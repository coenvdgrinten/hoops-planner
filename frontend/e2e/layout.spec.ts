import { test, expect } from "@playwright/test";

test.describe("Layout", () => {
  test("loads the application", async ({ page }) => {
    await page.goto("/");

    // Top bar elements
    await expect(page.getByAltText("BC Vido")).toBeVisible();
    await expect(page.getByText("Sixth Man")).toHaveCount(2);
    await expect(page.getByText("BC Vido")).toBeVisible();

    // Import buttons
    await expect(page.getByRole("button", { name: "Import Schedule" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Import Members" })).toBeVisible();

    // Sidebar navigation
    await expect(page.getByRole("button", { name: "Schedule Planner" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Statistics" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Members" })).toBeVisible();

    // Planner view is default
    await expect(page.getByRole("button", { name: "Schedule Planner" })).toHaveClass(/active/);
  });

  test("shows empty state when no season selected", async ({ page }) => {
    await page.goto("/");

    // Should show empty state message
    await expect(page.getByRole("heading", { name: "Welcome to Sixth Man" })).toBeVisible();
  });

  test("navigates between views", async ({ page }) => {
    await page.goto("/");

    // Click Statistics
    await page.getByRole("button", { name: "Statistics" }).click();
    await expect(page.getByRole("button", { name: "Statistics" })).toHaveClass(/active/);

    // Click Members nav button
    const membersBtn = page.getByRole("navigation").getByRole("button", { name: "Member Roster" });
    await membersBtn.click();
    await expect(membersBtn).toHaveClass(/active/);

    // Click back to Planner
    await page.getByRole("navigation").getByRole("button", { name: "Schedule Planner" }).click();
    await expect(page.getByRole("navigation").getByRole("button", { name: "Schedule Planner" })).toHaveClass(/active/);
  });
});
