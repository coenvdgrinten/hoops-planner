import { test, expect } from "@playwright/test";

test.describe("Season Selector", () => {
  const seasonName = `Season-${Date.now()}`;

  test.beforeEach(async ({ request }) => {
    // Seed a season so the dropdown has options
    const scheduleCsv =
      "date,time,court,home_team,away_team\n2025-10-01,14:00,1,Team A,Team B";

    await request.post("/api/seasons/import_schedule/", {
      data: { season_name: seasonName, csv_text: scheduleCsv },
    });
  });

  test("shows custom dropdown toggle button", async ({ page }) => {
    await page.goto("/");

    // Toggle button should be visible
    const toggle = page.locator(".season-dropdown-toggle");
    await expect(toggle).toBeVisible();
  });

  test("opens dropdown menu on click", async ({ page }) => {
    await page.goto("/");

    const toggle = page.locator(".season-dropdown-toggle");
    await toggle.click();

    // Dropdown menu should appear
    const menu = page.locator(".season-dropdown-menu");
    await expect(menu).toBeVisible();
  });

  test("closes dropdown on clicking outside", async ({ page }) => {
    await page.goto("/");

    // Open dropdown
    await page.locator(".season-dropdown-toggle").click();
    await expect(page.locator(".season-dropdown-menu")).toBeVisible();

    // Click somewhere else (page background)
    await page.locator("body").click({ position: { x: 10, y: 10 } });

    // Menu should close
    await expect(page.locator(".season-dropdown-menu")).not.toBeVisible();
  });

  test("closes dropdown on pressing Escape", async ({ page }) => {
    await page.goto("/");

    // Open dropdown
    await page.locator(".season-dropdown-toggle").click();
    await expect(page.locator(".season-dropdown-menu")).toBeVisible();

    // Press Escape
    await page.keyboard.press("Escape");

    // Menu should close
    await expect(page.locator(".season-dropdown-menu")).not.toBeVisible();
  });

  test("selects a season from dropdown", async ({ page }) => {
    await page.goto("/");

    // Open and select by season name
    await page.locator(".season-dropdown-toggle").click();
    await page.locator(".season-dropdown-item").filter({ hasText: seasonName }).click();

    // Toggle button should show selected season
    const value = page.locator(".season-dropdown-value");
    await expect(value).toContainText(seasonName);

    // Games should appear
    await expect(page.getByText("Team A")).toBeVisible();
  });

  test("shows checkmark for selected season", async ({ page }) => {
    await page.goto("/");

    // Open dropdown, select a season
    await page.locator(".season-dropdown-toggle").click();
    await page.locator(".season-dropdown-item").filter({ hasText: seasonName }).click();

    // Re-open dropdown
    await page.locator(".season-dropdown-toggle").click();

    // Selected item should have checkmark
    await expect(page.locator(".season-check")).toBeVisible();
  });
});
