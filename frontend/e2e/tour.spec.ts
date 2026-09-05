import { test, expect, type Page } from "./fixtures";
import { authenticate, uniqueName } from "./helpers";

/**
 * Interactive guided tour (issue #8).
 *
 * Every other spec pre-seeds auth via `authenticate()` + a fresh browser
 * context, so the auto-starting tour never interferes with them. This spec
 * drives the two real flows:
 *  - no season yet → single-step "gate" tour pointing at the season picker,
 *  - with a season → full core-planning-loop tour, replayable via Help.
 *
 * The full-tour leg selects the demo season ("2025-2026") that global-setup
 * seeds; it has real games, so the game-card / task-chip steps are exercised
 * rather than skipped.
 */

const POPOVER = ".driver-popover";
const TITLE = ".driver-popover-title";
const NEXT_BTN = ".driver-popover-next-btn";
const CLOSE_BTN = ".driver-popover-close-btn";

const DEMO_SEASON = "2025-2026";

test.describe("Guided tour", () => {
  // Some steps wait up to 3 s for elements that don't exist before skipping.
  test.setTimeout(60_000);

  test.beforeEach(async ({ request, page }) => {
    await authenticate(request, page, uniqueName("to-"));
  });

  /**
   * Reset the tour's completed flag for this page. The shared auth helper
   * marks the tour completed (so other specs never see it); this spec is
   * ABOUT the tour, so it manages the flag itself. Note: addInitScript also
   * re-runs on every reload, so it must NOT be used in tests that rely on
   * the flag surviving a reload.
   */
  async function resetTourFlag(page: Page) {
    await page.addInitScript(() => localStorage.removeItem("tour-completed"));
  }

  test("runs the gate tour without a season, then the full tour via Help", async ({
    page,
  }: {
    page: Page;
  }) => {
    await resetTourFlag(page);
    await page.goto("/");

    // Auto-start: the single-step gate tour points at the season selector.
    await expect(page.locator(POPOVER)).toBeVisible();
    await expect(page.locator(TITLE)).toHaveText("Pick a season");

    // Dismissing the tour must NOT mark it completed (it was interrupted).
    await page.locator(CLOSE_BTN).click();
    await expect(page.locator(POPOVER)).toHaveCount(0);
    expect(await page.evaluate(() => localStorage.getItem("tour-completed"))).toBe(
      null,
    );

    // Select the seeded demo season (already present in the dropdown).
    await page.getByTestId("season-dropdown-toggle").click();
    await page.getByRole("button", { name: DEMO_SEASON, exact: true }).click();

    // Help replays the full tour for the selected season.
    await page.getByRole("button", { name: "Help" }).click();
    await expect(page.locator(TITLE)).toHaveText("Pick a season");

    // Walk to the end. The demo season has games, so every step is present:
    // season → fill bar → game card → task chip → export.
    //
    // Under heavy parallel load a Next click can occasionally be lost
    // (the popover does not advance), so each click is verified: the title
    // must change to a step we have not seen yet, or we click again.
    const seen = new Set<string>();
    for (let i = 0; i < 8; i++) {
      const title = (await page.locator(TITLE).textContent())?.trim() ?? "";
      if (title === "Share the schedule") break;
      seen.add(title);
      await page.locator(NEXT_BTN).click();
      await expect
        .poll(
          async () => (await page.locator(TITLE).textContent())?.trim(),
          { timeout: 5_000 },
        )
        .not.toBe(seen.size > 0 ? [...seen].pop()! : "");
    }
    await expect(page.locator(TITLE)).toHaveText("Share the schedule");

    // Finishing marks the tour completed in this browser.
    await page.locator(NEXT_BTN).click();
    await expect(page.locator(POPOVER)).toHaveCount(0);
    expect(await page.evaluate(() => localStorage.getItem("tour-completed"))).toBe(
      "1",
    );
  });

  test("does not auto-start again once completed", async ({ page, context }) => {
    await resetTourFlag(page);
    await page.goto("/");
    // First visit: the (single-step) gate tour runs.
    await expect(page.locator(POPOVER)).toBeVisible();
    await page.locator(NEXT_BTN).click(); // Done → tour finished
    await expect(page.locator(POPOVER)).toHaveCount(0);

    // A brand-new tab in the same browser profile shares localStorage but
    // none of this page's init scripts: the completed flag must survive, so
    // no tour on this "returning visit".
    const returning = await context.newPage();
    await returning.goto("/");
    await expect(returning.locator(POPOVER)).toHaveCount(0);
  });
});
