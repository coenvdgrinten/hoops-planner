import { test, expect } from "./fixtures";
import { authenticate, uniqueName } from "./helpers";

const API = "/api";

/**
 * Browse saved schedule versions (issue #6).
 *
 * The Planner gains a Versions tab next to Schedule: it lists a season's
 * snapshots newest first with a freshness line, shows metadata + a download
 * for the selected version, and the downloaded file is byte-for-byte the one
 * captured at save time.
 */
test.describe("Version browser", () => {
  let seasonName: string;
  let token: string;
  let teamA: string;
  let teamB: string;

  test.beforeEach(async ({ request, page }) => {
    // Own season + teams per test (uniqueName): seasons/teams are keyed by
    // name globally, so fixed names would collide across parallel workers.
    token = await authenticate(request, page, uniqueName("vb-"));
    seasonName = uniqueName("Browse-");
    teamA = uniqueName("Team A");
    teamB = uniqueName("Team B");

    const scheduleCsv =
      `date,time,court,home_team,away_team\n2025-10-01,14:00,1,${teamA},${teamB}`;
    const schedRes = await request.post(`${API}/seasons/import_schedule/`, {
      headers: { Authorization: `Token ${token}` },
      data: { season_name: seasonName, csv_text: scheduleCsv },
    });
    expect(schedRes.status(), "import_schedule should succeed").toBe(201);
  });

  async function selectSeason(page: import("@playwright/test").Page) {
    await page.getByTestId("season-dropdown-toggle").click();
    await page
      .getByTestId("season-dropdown-menu")
      .getByText(seasonName, { exact: true })
      .click();
  }

  /** Save a snapshot via the CSV export dialog; returns the downloaded bytes. */
  async function saveVersionViaExport(
    page: import("@playwright/test").Page,
    note: string,
  ): Promise<Buffer> {
    await page.getByTestId("export-csv-btn").click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 10_000 });
    await dialog.getByTestId("save-version-checkbox").check();
    if (note) {
      await dialog.getByTestId("version-note-input").fill(note);
    }
    const downloadPromise = page.waitForEvent("download");
    await dialog.getByTestId("pdf-warning-export-btn").click();
    const download = await downloadPromise;
    return readStream(download);
  }

  async function readStream(download: import("@playwright/test").Download) {
    // Playwright saves downloads to a temp file; read it back for byte
    // comparison.
    const fs = await import("node:fs/promises");
    return fs.readFile(await download.path());
  }

  test("Planner shows Schedule (default) and Versions tabs", async ({ page }) => {
    await page.goto("/");
    await selectSeason(page);

    const scheduleTab = page.getByTestId("planner-tab-schedule");
    const versionsTab = page.getByTestId("planner-tab-versions");
    await expect(scheduleTab).toBeVisible();
    await expect(versionsTab).toBeVisible();
    // Schedule is the default tab.
    await expect(scheduleTab).toHaveAttribute("aria-selected", "true");
    await expect(versionsTab).toHaveAttribute("aria-selected", "false");
  });

  test("empty state points at the export dialog checkbox", async ({ page }) => {
    await page.goto("/");
    await selectSeason(page);
    await page.getByTestId("planner-tab-versions").click();

    const empty = page.getByTestId("versions-empty");
    await expect(empty).toBeVisible();
    await expect(empty).toContainText("save a schedule version");
  });

  test("lists versions newest first with note and freshness line", async ({
    page,
  }) => {
    await page.goto("/");
    await selectSeason(page);

    await saveVersionViaExport(page, "first send");
    // Drift the live schedule so v2 differs from v1: add a second game.
    const driftCsv =
      `date,time,court,home_team,away_team\n2025-10-08,14:00,1,${teamA},${teamB}`;
    await page.request.post(`${API}/seasons/import_schedule/`, {
      headers: { Authorization: `Token ${token}` },
      data: { season_name: seasonName, csv_text: driftCsv },
    });
    await saveVersionViaExport(page, "second send");

    await page.getByTestId("planner-tab-versions").click();

    // Freshness: live matches the latest (v2), since we just exported it.
    await expect(page.getByTestId("versions-freshness")).toHaveText(
      "Live schedule matches v2.",
    );
    // Newest first: v2 above v1, notes intact.
    const row2 = page.getByTestId("version-row-2");
    const row1 = page.getByTestId("version-row-1");
    await expect(row2).toBeVisible();
    await expect(row1).toBeVisible();
    await expect(row2).toContainText("second send");
    await expect(row1).toContainText("first send");
    expect(
      await row2.boundingBox(),
    ).not.toBeNull();
    const b2 = (await row2.boundingBox())!;
    const b1 = (await row1.boundingBox())!;
    expect(b2.y).toBeLessThan(b1.y);
  });

  test("selecting a version shows metadata and a working download", async ({
    page,
  }) => {
    await page.goto("/");
    await selectSeason(page);

    const originalBytes = await saveVersionViaExport(page, "sent to managers");

    await page.getByTestId("planner-tab-versions").click();
    await page.getByTestId("version-row-1").click();

    const detail = page.getByTestId("version-detail");
    await expect(detail).toBeVisible();
    await expect(detail).toContainText("Version v1");
    await expect(detail).toContainText("sent to managers");
    await expect(detail).toContainText("CSV");

    const downloadPromise = page.waitForEvent("download");
    await page.getByTestId("version-download-1").click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe(`schedule_${seasonName}_v1.csv`);

    // Byte-for-byte fidelity: identical to what was distributed on export.
    const storedBytes = await readStream(download);
    expect(storedBytes.equals(originalBytes)).toBe(true);
  });

  test("freshness flips after the live schedule changes", async ({ page }) => {
    await page.goto("/");
    await selectSeason(page);

    await saveVersionViaExport(page, "");
    await page.getByTestId("planner-tab-versions").click();
    await expect(page.getByTestId("versions-freshness")).toHaveText(
      "Live schedule matches v1.",
    );

    // Add a game → the live schedule no longer matches v1.
    const driftCsv =
      `date,time,court,home_team,away_team\n2025-10-08,14:00,1,${teamA},${teamB}`;
    await page.request.post(`${API}/seasons/import_schedule/`, {
      headers: { Authorization: `Token ${token}` },
      data: { season_name: seasonName, csv_text: driftCsv },
    });
    // Refresh the list (the query refetches when the tab re-renders; force it
    // by switching tabs, which is how a user would notice the change).
    await page.getByTestId("planner-tab-schedule").click();
    await page.getByTestId("planner-tab-versions").click();

    await expect(page.getByTestId("versions-freshness")).toHaveText(
      "Live schedule has changed since v1.",
    );
  });

  test("switching seasons switches the version list", async ({
    page,
    request,
  }) => {
    const otherSeason = uniqueName("Other-");
    const otherCsv =
      `date,time,court,home_team,away_team\n2025-11-01,14:00,1,${teamA},${teamB}`;
    await request.post(`${API}/seasons/import_schedule/`, {
      headers: { Authorization: `Token ${token}` },
      data: { season_name: otherSeason, csv_text: otherCsv },
    });

    await page.goto("/");
    await selectSeason(page);
    await saveVersionViaExport(page, "");

    // Switch to the other season: it has no versions yet.
    await page.getByTestId("season-dropdown-toggle").click();
    await page
      .getByTestId("season-dropdown-menu")
      .getByText(otherSeason, { exact: true })
      .click();
    await page.getByTestId("planner-tab-versions").click();

    await expect(page.getByTestId("versions-empty")).toBeVisible();
  });
});
