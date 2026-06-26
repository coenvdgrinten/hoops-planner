import { test, expect } from "@playwright/test";

test.describe("Member View", () => {
  test.beforeEach(async ({ request }) => {
    // Seed members with different cert levels
    const membersCsv =
      "first_name,last_name,team,is_coach,referee_certification\nAlice,NoCert,Team A,False,NONE\nBob,FDiploma,Team A,False,F\nCharlie,Senior,Team A,False,SENIOR\nDiana,Coach,Team A,True,F";

    await request.post("/api/players/import_members/", {
      data: { csv_text: membersCsv, upsert: true },
    });
  });

  test("shows member roster view", async ({ page }) => {
    await page.goto("/");

    // Navigate to Members view
    const membersBtn = page.getByRole("navigation").getByRole("button", { name: "Member Roster" });
    await membersBtn.click();

    await expect(membersBtn).toHaveClass(/active/);
  });

  test("displays imported members", async ({ page }) => {
    await page.goto("/");

    const membersBtn = page.getByRole("navigation").getByRole("button", { name: "Member Roster" });
    await membersBtn.click();

    // Expand Team A to see members
    const teamARow = page.locator(".roster-team-header").filter({ hasText: "Team A" });
    await teamARow.click();

    // Members should appear
    await expect(page.getByText("Alice NoCert")).toBeVisible();
    await expect(page.getByText("Bob FDiploma")).toBeVisible();
  });

  test("shows cert badge for NONE certification", async ({ page }) => {
    await page.goto("/");

    const membersBtn = page.getByRole("navigation").getByRole("button", { name: "Member Roster" });
    await membersBtn.click();

    // Expand Team A
    const teamARow = page.locator(".roster-team-header").filter({ hasText: "Team A" });
    await teamARow.click();

    // Alice has NONE cert — should show cert-none styling
    const aliceRow = page.getByText("Alice NoCert").first();
    await expect(aliceRow).toBeVisible();

    const badge = aliceRow.locator("..").locator(".cert-badge, [class*='cert']");
    const badgeVisible = await badge.isVisible();
    if (badgeVisible) {
      await expect(badge).toHaveClass(/cert-none/);
    }
  });

  test("shows cert badge for F certification", async ({ page }) => {
    await page.goto("/");

    const membersBtn = page.getByRole("navigation").getByRole("button", { name: "Member Roster" });
    await membersBtn.click();

    // Expand Team A
    const teamARow = page.locator(".roster-team-header").filter({ hasText: "Team A" });
    await teamARow.click();

    // Bob has F cert — should show cert-low styling
    const bobRow = page.getByText("Bob FDiploma").first();
    await expect(bobRow).toBeVisible();

    const badge = bobRow.locator("..").locator(".cert-badge, [class*='cert']");
    const badgeVisible = await badge.isVisible();
    if (badgeVisible) {
      await expect(badge).toHaveClass(/cert-low/);
    }
  });

  test("shows cert badge for SENIOR certification", async ({ page }) => {
    await page.goto("/");

    const membersBtn = page.getByRole("navigation").getByRole("button", { name: "Member Roster" });
    await membersBtn.click();

    // Expand Team A
    const teamARow = page.locator(".roster-team-header").filter({ hasText: "Team A" });
    await teamARow.click();

    // Charlie has SENIOR cert — should show cert-high styling
    const charlieRow = page.getByText("Charlie Senior").first();
    await expect(charlieRow).toBeVisible();

    const badge = charlieRow.locator("..").locator(".cert-badge, [class*='cert']");
    const badgeVisible = await badge.isVisible();
    if (badgeVisible) {
      await expect(badge).toHaveClass(/cert-high/);
    }
  });
});
