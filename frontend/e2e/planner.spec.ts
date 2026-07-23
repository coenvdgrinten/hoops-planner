import { test, expect, type Page } from "@playwright/test";
import { authenticate } from "./helpers";

const API = "/api";

test.describe("Planner", () => {
  let seasonName: string;

  test.beforeEach(async ({ request, page }) => {
    const token = await authenticate(request, page, `pl-${Date.now()}`);
    seasonName = `Planner-${Date.now()}`;

    // Seed data via API before each test
    const scheduleCsv =
      "date,time,court,home_team,away_team\n2025-10-01,14:00,1,Team A,Team B\n2025-10-01,14:00,2,Team C,Team D";

    const membersCsv =
      "first_name,last_name,team,is_coach,referee_certification\nAlice,Refsen,Team A,True,SENIOR\nBob,Player,Team A,False,\nCharlie,Coachsen,Team C,True,F\nDiana,Referee,Team A,False,F\nEve,Player,Team C,False,NONE";

    // Import schedule (creates season automatically)
    const schedRes = await request.post(`${API}/seasons/import_schedule/`, {
      headers: { Authorization: `Token ${token}` },
      data: { season_name: seasonName, csv_text: scheduleCsv },
    });
    expect(schedRes.status(), "import_schedule should succeed").toBe(201);

    // Import members
    const memRes = await request.post(`${API}/players/import_members/`, {
      headers: { Authorization: `Token ${token}` },
      data: { csv_text: membersCsv, upsert: true },
    });
    expect(memRes.status(), "import_members should succeed").toBe(201);
  });

  async function selectSeason(page: Page) {
    await page.getByTestId("season-dropdown-toggle").click();
    await page.getByTestId("season-dropdown-menu").getByText(seasonName, { exact: true }).click();
  }

  test("displays games after selecting a season", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    // Games should appear
    await expect(page.getByText("Team A")).toBeVisible();
    await expect(page.getByText("Team B")).toBeVisible();
  });

  test("groups games by date", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    // Date group label should be visible
    await expect(page.getByTestId("date-label").first()).toBeVisible();
  });

  test("shows age badges on game cards", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    // Age badges should be visible
    await expect(page.getByTestId("age-badge").first()).toBeVisible();
  });

  test("shows task chips on game cards", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    // Task chips should appear
    await expect(page.getByTestId(/^task-chip-\d+$/).first()).toBeVisible({ timeout: 10_000 });
  });

  test("opens assignment panel when clicking a task chip", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    // Click on a task chip
    await page.getByTestId(/^task-chip-\d+$/).first().click();

    // Assignment panel should appear
    const panel = page.getByTestId("assignment-panel");
    await expect(panel).toBeVisible({ timeout: 10_000 });
  });

  test("shows assigned state after adding a player", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    // Click on a task chip to open panel
    await page.getByTestId(/^task-chip-\d+$/).first().click();
    const panel = page.getByTestId("assignment-panel");
    await expect(panel).toBeVisible({ timeout: 10_000 });

    // Find a candidate to add
    const addBtn = panel.getByTestId(/^add-candidate-\d+$/).first();
    const addBtnVisible = await addBtn.isVisible();

    if (addBtnVisible) {
      await addBtn.click();

      // Close panel and check for filled state
      await panel.getByTestId("assignment-panel-close").click();

      // The game card should show assigned state
      await expect(page.getByTestId(/^task-chip-\d+$/).first()).toHaveClass(/filled/, {
        timeout: 10_000,
      });
    }
  });

  test("exports the schedule as CSV", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    const downloadPromise = page.waitForEvent("download");
    await page.getByTestId("export-csv-btn").click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe(`schedule_${seasonName}.csv`);

    const stream = await download.createReadStream();
    let csv = "";
    for await (const chunk of stream) {
      csv += chunk.toString();
    }
    expect(csv).toContain("date,time,court");
    expect(csv).toContain("Team A");
  });

  test("exports the schedule as PDF", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    const downloadPromise = page.waitForEvent("download");
    await page.getByTestId("export-pdf-btn").click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe(`schedule_${seasonName}.pdf`);

    const stream = await download.createReadStream();
    let pdf = "";
    for await (const chunk of stream) {
      pdf += chunk.toString();
    }
    expect(pdf).toContain("%PDF");
  });

  test("exports the schedule as calendar (.ics)", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    const downloadPromise = page.waitForEvent("download");
    await page.getByTestId("export-ics-btn").click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe(`schedule_${seasonName}.ics`);

    const stream = await download.createReadStream();
    let ics = "";
    for await (const chunk of stream) {
      ics += chunk.toString();
    }
    expect(ics).toContain("BEGIN:VCALENDAR");
    expect(ics).toContain("BEGIN:VEVENT");
    expect(ics).toContain("END:VCALENDAR");
    expect(ics).toContain("Team A");
    expect(ics).toContain("Team B");
  });
});
