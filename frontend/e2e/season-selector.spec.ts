import { test, expect, type Page } from "./fixtures";
import { authenticate, uniqueName } from "./helpers";

const API = "/api";

test.describe("Season Selector", () => {
  let seasonName: string;

  test.beforeEach(async ({ request, page }) => {
    const token = await authenticate(request, page, uniqueName("ss-"));
    seasonName = uniqueName("Season-");

    // Seed a season so the dropdown has options (unique team names — teams
    // are global rows keyed by name in the backend)
    const scheduleCsv =
      `date,time,court,home_team,away_team\n2025-10-01,14:00,1,${uniqueName("Team A")},${uniqueName("Team B")}`;

    const res = await request.post(`${API}/seasons/import_schedule/`, {
      headers: { Authorization: `Token ${token}` },
      data: { season_name: seasonName, csv_text: scheduleCsv },
    });
    expect(res.status(), "import_schedule should succeed").toBe(201);
  });

  test("shows custom dropdown toggle button", async ({ page }: { page: Page }) => {
    await page.goto("/");

    // Toggle button should be visible
    const toggle = page.getByTestId("season-dropdown-toggle");
    await expect(toggle).toBeVisible();
  });

  test("opens dropdown menu on click", async ({ page }: { page: Page }) => {
    await page.goto("/");

    const toggle = page.getByTestId("season-dropdown-toggle");
    await toggle.click();

    // Dropdown menu should appear
    const menu = page.getByTestId("season-dropdown-menu");
    await expect(menu).toBeVisible();
  });

  test("closes dropdown on clicking outside", async ({ page }: { page: Page }) => {
    await page.goto("/");

    // Open dropdown
    await page.getByTestId("season-dropdown-toggle").click();
    await expect(page.getByTestId("season-dropdown-menu")).toBeVisible();

    // Click somewhere else (page background)
    await page.locator("body").click({ position: { x: 10, y: 10 } });

    // Menu should close
    await expect(page.getByTestId("season-dropdown-menu")).not.toBeVisible();
  });

  test("closes dropdown on pressing Escape", async ({ page }: { page: Page }) => {
    await page.goto("/");

    // Open dropdown
    await page.getByTestId("season-dropdown-toggle").click();
    await expect(page.getByTestId("season-dropdown-menu")).toBeVisible();

    // Press Escape
    await page.keyboard.press("Escape");

    // Menu should close
    await expect(page.getByTestId("season-dropdown-menu")).not.toBeVisible();
  });

  test("selects a season from dropdown", async ({ page }: { page: Page }) => {
    await page.goto("/");

    // Open and select by season name
    await page.getByTestId("season-dropdown-toggle").click();
    await page.getByTestId("season-dropdown-menu").getByText(seasonName, { exact: true }).click();

    // Toggle button should show selected season
    const value = page.getByTestId("season-dropdown-value");
    await expect(value).toContainText(seasonName);

    // Games should appear
    await expect(page.getByText("Team A")).toBeVisible();
  });

  test("shows checkmark for selected season", async ({ page }: { page: Page }) => {
    await page.goto("/");

    // Open dropdown, select a season
    await page.getByTestId("season-dropdown-toggle").click();
    await page.getByTestId("season-dropdown-menu").getByText(seasonName, { exact: true }).click();

    // Re-open dropdown
    await page.getByTestId("season-dropdown-toggle").click();

    // Selected item should have checkmark
    await expect(page.getByTestId("season-check")).toBeVisible();
  });
});
