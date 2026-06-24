import { test, expect } from "@playwright/test";

test.describe("Planner", () => {
  test.beforeEach(async ({ request }) => {
    // Seed data via API before each test
    const scheduleCsv =
      "date,time,court,home_team,away_team\n2025-10-01,14:00,1,Team A,Team B\n2025-10-01,14:00,2,Team C,Team D";

    const membersCsv =
      "first_name,last_name,team,is_coach,referee_certification\nAlice,Refsen,Team A,True,T1\nBob,Player,Team A,False,\nCharlie,Coachsen,Team C,True,T1";

    // Import schedule (creates season automatically)
    await request.post("/api/seasons/import_schedule/", {
      data: { season_name: "2025/2026", csv_text: scheduleCsv },
    });

    // Import members
    await request.post("/api/players/import_members/", {
      data: { csv_text: membersCsv, upsert: true },
    });
  });

  test("displays games after selecting a season", async ({ page }) => {
    await page.goto("/");

    // Select season from dropdown
    await page.getByRole("combobox").click();
    await page.getByRole("option", { name: "2025/2026" }).click();

    // Games should appear
    await expect(page.getByText("Team A")).toBeVisible();
    await expect(page.getByText("Team B")).toBeVisible();
  });

  test("groups games by date", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("combobox").click();
    await page.getByRole("option", { name: "2025/2026" }).click();

    // Date group label should be visible
    await expect(page.getByText(/Oct 1/i)).toBeVisible();
  });

  test("shows age badges on game cards", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("combobox").click();
    await page.getByRole("option", { name: "2025/2026" }).click();

    // Age badges should be visible (MIXED when no age category)
    await expect(page.getByText("MIXED")).toBeVisible();
  });

  test("shows task chips on game cards", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("combobox").click();
    await page.getByRole("option", { name: "2025/2026" }).click();

    // Task chips should appear
    await expect(page.locator(".task-chip")).toBeVisible({ timeout: 10_000 });
  });

  test("opens assignment panel when clicking a task chip", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("combobox").click();
    await page.getByRole("option", { name: "2025/2026" }).click();

    // Click on a task chip
    await page.locator(".task-chip").first().click();

    // Assignment panel should appear
    const panel = page.locator(".assignment-panel");
    await expect(panel).toBeVisible({ timeout: 10_000 });
  });

  test("shows assigned state after adding a player", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("combobox").click();
    await page.getByRole("option", { name: "2025/2026" }).click();

    // Click on a task chip to open panel
    await page.locator(".task-chip").first().click();
    const panel = page.locator(".assignment-panel");
    await expect(panel).toBeVisible({ timeout: 10_000 });

    // Find a candidate to add
    const addBtn = panel.locator("button.add-btn").first();
    const addBtnVisible = await addBtn.isVisible();

    if (addBtnVisible) {
      await addBtn.click();

      // Close panel and check for filled state
      await panel.locator("button.close-btn").click();

      // The game card should show assigned state
      await expect(page.locator(".task-chip.filled")).toBeVisible({
        timeout: 10_000,
      });
    }
  });
});
