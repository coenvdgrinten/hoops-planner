import { test, expect, type Page } from "./fixtures";
import { authenticate, uniqueName } from "./helpers";

test.describe("Import Modal", () => {
  test.beforeEach(async ({ request, page }) => {
    await authenticate(request, page, uniqueName("im-"));
  });

  test("opens schedule import modal", async ({ page }: { page: Page }) => {
    await page.goto("/");

    await page.getByRole("button", { name: "Import Schedule" }).click();

    // Modal should be visible
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible();
    await expect(modal.getByRole("heading", { name: "Import Schedule" })).toBeVisible();
  });

  test("opens members import modal", async ({ page }: { page: Page }) => {
    await page.goto("/");

    await page.getByRole("button", { name: "Import Members" }).click();

    // Modal should be visible
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible();
    await expect(modal.getByRole("heading", { name: "Import Members" })).toBeVisible();
  });

  test("closes modal on cancel", async ({ page }: { page: Page }) => {
    await page.goto("/");

    await page.getByRole("button", { name: "Import Schedule" }).click();
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible();

    // Close via cancel or Escape
    await page.keyboard.press("Escape");
    await expect(modal).not.toBeVisible();
  });
});
