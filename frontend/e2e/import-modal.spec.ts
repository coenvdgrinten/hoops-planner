import { test, expect } from "@playwright/test";

test.describe("Import Modal", () => {
  test("opens schedule import modal", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("button", { name: "Import Schedule" }).click();

    // Modal should be visible
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible();
    await expect(modal.getByRole("heading", { name: "Import Schedule" })).toBeVisible();
  });

  test("opens members import modal", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("button", { name: "Import Members" }).click();

    // Modal should be visible
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible();
    await expect(modal.getByRole("heading", { name: "Import Members" })).toBeVisible();
  });

  test("closes modal on cancel", async ({ page }) => {
    await page.goto("/");

    await page.getByRole("button", { name: "Import Schedule" }).click();
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible();

    // Close via cancel or Escape
    await page.keyboard.press("Escape");
    await expect(modal).not.toBeVisible();
  });
});
