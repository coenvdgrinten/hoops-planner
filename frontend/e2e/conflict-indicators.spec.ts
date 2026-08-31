import { test, expect, type Page } from "./fixtures";
import { authenticate, uniqueName } from "./helpers";

const API = "/api";

/**
 * Conflict indicators (issue #1): when a roster or schedule change makes an
 * existing assignment invalid, the planner must flag it — red chip with the
 * reason, plus a season-wide conflict counter in the header.
 *
 * Two mutation vectors are covered end-to-end through the real UI:
 *   1. Schedule change: an away game is imported for the assigned player's
 *      team on the same day.
 *   2. Roster change: the assigned player's team is moved to the game's own
 *      team via a members re-import.
 */
test.describe("Conflict indicators", () => {
  let seasonName: string;
  let token: string;
  let teamA: string;
  let teamB: string;
  let aliceFirst: string;
  let carolFirst: string;

  test.beforeEach(async ({ request, page }) => {
    // Unique names per test (see uniqueName): the backend keys teams by name
    // and players by first+last name globally.
    seasonName = uniqueName("Conf-");
    teamA = uniqueName("Team A");
    teamB = uniqueName("Team B");
    aliceFirst = uniqueName("Alice");
    carolFirst = uniqueName("Carol");
    token = await authenticate(request, page, uniqueName("conf-"));

    // One home game for teamB; alice (teamA) will staff its scorer slot.
    const scheduleCsv =
      "date,time,court,home_team,away_team\n" +
      `2025-10-01,14:00,1,${teamB},${uniqueName("Opponent")}`;

    const membersCsv =
      "first_name,last_name,team,is_coach,referee_certification\n" +
      `${aliceFirst},PlayerA,${teamA},False,F\n` +
      `${carolFirst},Other,${uniqueName("Team C")},False,NONE`;

    const schedRes = await request.post(`${API}/seasons/import_schedule/`, {
      headers: { Authorization: `Token ${token}` },
      data: { season_name: seasonName, csv_text: scheduleCsv },
    });
    expect(schedRes.status(), "import_schedule should succeed").toBe(201);

    const memRes = await request.post(`${API}/players/import_members/`, {
      headers: { Authorization: `Token ${token}` },
      data: { csv_text: membersCsv, upsert: true },
    });
    expect(memRes.status(), "import_members should succeed").toBe(201);
  });

  async function selectSeason(page: Page) {
    await page.getByTestId("season-dropdown-toggle").click();
    await page
      .getByTestId("season-dropdown-menu")
      .getByText(seasonName, { exact: true })
      .click();
  }

  /** Open the scorer chip of the (single) game and assign alice to it.

   * Uses the panel's Teams & Members roster (search + expand + add) rather
   * than the suggested-candidates list: suggestions are capped at 5 and the
   * shared dev database holds many zero-task players, so alice would not be
   * guaranteed to appear there.
   */
  async function assignAliceToScorer(page: Page) {
    const scorerChip = page
      .getByTestId(/^task-chip-\d+$/)
      .filter({ hasText: "SCORER" });
    await expect(scorerChip).toBeVisible({ timeout: 10_000 });
    await scorerChip.click();

    const panel = page.getByTestId("assignment-panel");
    await expect(panel).toBeVisible();

    // Narrow the roster to alice, expand her team, and add her.
    await panel.getByLabel("Search member or team").fill(aliceFirst);
    await panel
      .getByRole("button", { name: new RegExp(teamA) })
      .first()
      .click();
    const aliceRow = panel
      .locator('[data-testid^="member-row-"]')
      .filter({ hasText: aliceFirst });
    await expect(aliceRow).toBeVisible();
    await aliceRow.getByTestId(/^add-member-\d+$/).click();

    await panel.getByTestId("assignment-panel-close").click();
    await expect(scorerChip).toHaveClass(/filled/, { timeout: 10_000 });
  }

  async function importViaModal(
    page: Page,
    kind: "Schedule" | "Members",
    csv: string,
  ) {
    await page.getByRole("button", { name: `Import ${kind}` }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    if (kind === "Schedule") {
      await dialog.locator("#import-season-name").fill(seasonName);
    }
    await dialog.locator("textarea").fill(csv);
    await dialog.getByRole("button", { name: `Import ${kind}` }).click();
    await expect(dialog).toBeHidden({ timeout: 15_000 });
  }

  test("chip turns red when an away game is added for the player's team", async ({
    page,
  }) => {
    await page.goto("/");
    await selectSeason(page);
    await assignAliceToScorer(page);

    // No conflict yet.
    await expect(page.getByTestId("conflict-count")).not.toBeVisible();

    // Import a schedule adding an AWAY game for alice's team the same day.
    await importViaModal(
      page,
      "Schedule",
      "date,time,court,home_team,away_team,game_type\n" +
        `2025-10-01,10:00,1,${teamA},${uniqueName("Away Opp")},AWAY`,
    );

    const scorerChip = page
      .getByTestId(/^task-chip-\d+$/)
      .filter({ hasText: "SCORER" });
    await expect(scorerChip).toHaveClass(/conflict/, { timeout: 10_000 });
    await expect(scorerChip).toHaveAttribute(
      "title",
      /Team has an away game on the same day/,
    );

    // Header counter reflects the single conflicting assignment.
    const badge = page.getByTestId("conflict-count");
    await expect(badge).toBeVisible();
    await expect(badge).toContainText("1 conflict");
  });

  test("chip turns red when the player's team changes to the game's team", async ({
    page,
  }) => {
    await page.goto("/");
    await selectSeason(page);
    await assignAliceToScorer(page);

    await expect(page.getByTestId("conflict-count")).not.toBeVisible();

    // Re-import members with alice moved onto teamB (the game's own team).
    await importViaModal(
      page,
      "Members",
      "first_name,last_name,team,is_coach,referee_certification\n" +
        `${aliceFirst},PlayerA,${teamB},False,F`,
    );

    const scorerChip = page
      .getByTestId(/^task-chip-\d+$/)
      .filter({ hasText: "SCORER" });
    await expect(scorerChip).toHaveClass(/conflict/, { timeout: 10_000 });
    await expect(scorerChip).toHaveAttribute(
      "title",
      /Cannot be assigned to own team's game/,
    );

    const badge = page.getByTestId("conflict-count");
    await expect(badge).toBeVisible();
    await expect(badge).toContainText("1 conflict");
  });
});
