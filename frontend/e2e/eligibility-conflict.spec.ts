import { test, expect, type Page } from "./fixtures";
import { authenticate, fetchAllPages, uniqueName } from "./helpers";

const API = "/api";

test.describe("Eligibility - same time conflict", () => {
  let seasonName: string;
  let token: string;
  let teamA: string;
  let teamB: string;
  let aliceFirst: string;
  let bobFirst: string;

  test.beforeEach(async ({ request, page }) => {
    // Unique names per test (see uniqueName): the backend matches teams by
    // name and players by first+last name GLOBALLY, so fixed names would be
    // shared rows across parallel tests — and these tests assert on the
    // absence of specific players, which a concurrent import moving a shared
    // row would break.
    seasonName = uniqueName("Elig-");
    teamA = uniqueName("Team A");
    teamB = uniqueName("Team B");
    aliceFirst = uniqueName("Alice");
    bobFirst = uniqueName("Bob");
    token = await authenticate(request, page, seasonName);

    // Two teams with HOME games at the exact same time
    const scheduleCsv =
      "date,time,court,home_team,away_team\n" +
      `2025-10-01,14:00,1,${teamA},${uniqueName("Opponent A")}\n` +
      `2025-10-01,14:00,2,${teamB},${uniqueName("Opponent B")}`;

    // Players on our two teams plus a third team (eligible candidate)
    const membersCsv =
      "first_name,last_name,team,is_coach,referee_certification\n" +
      `${aliceFirst},PlayerA,${teamA},False,F\n` +
      `${bobFirst},PlayerB,${teamB},False,F\n` +
      `${uniqueName("Charlie")},Other,${uniqueName("Team C")},False,F`;

    const schedRes = await request.post(`${API}/seasons/import_schedule/`, {
      headers: { Authorization: `Token ${token}` },
      data: { season_name: seasonName, csv_text: scheduleCsv },
    });
    expect(schedRes.status()).toBe(201);

    const memRes = await request.post(`${API}/players/import_members/`, {
      headers: { Authorization: `Token ${token}` },
      data: { csv_text: membersCsv, upsert: true },
    });
    expect(memRes.status()).toBe(201);
  });

  async function selectSeason(page: Page) {
    await page.getByTestId("season-dropdown-toggle").click();
    await page.getByTestId("season-dropdown-menu").getByText(seasonName, { exact: true }).click();
  }

  test("players from Team B should NOT be eligible for Team A tasks when both games are at same time", async ({ page }) => {
    await page.goto("/");
    await selectSeason(page);

    // Click on a task chip for our home team's game (first game card)
    const teamACard = page.getByText(teamA).first();
    await expect(teamACard).toBeVisible({ timeout: 10_000 });

    // Find the task chips in the game card
    const taskChips = page.getByTestId(/^task-chip-\d+$/);
    await expect(taskChips.first()).toBeVisible({ timeout: 10_000 });

    // Click the first task chip to open assignment panel
    await taskChips.first().click();

    const panel = page.getByTestId("assignment-panel");
    await expect(panel).toBeVisible({ timeout: 10_000 });

    // Our Team B player should NOT appear because Team B has a game at the same time
    const bobInPanel = panel.getByText(bobFirst);
    await expect(bobInPanel).not.toBeVisible();

    // Our Team A player should also NOT appear because it's their own team's game
    const aliceInPanel = panel.getByText(aliceFirst);
    await expect(aliceInPanel).not.toBeVisible();
  });

  test("players from Team A should NOT be eligible for Team B tasks when both games are at same time", async ({ page }) => {
    await page.goto("/");
    await selectSeason(page);

    // Find our second team's game card
    const teamBCard = page.getByText(teamB).first();
    await expect(teamBCard).toBeVisible({ timeout: 10_000 });

    // Get all task chips and find ones in the card
    const taskChips = page.getByTestId(/^task-chip-\d+$/);
    await expect(taskChips.first()).toBeVisible({ timeout: 10_000 });

    // Click a task chip (any task chip should work for this test)
    await taskChips.nth(1).click();

    const panel = page.getByTestId("assignment-panel");
    await expect(panel).toBeVisible({ timeout: 10_000 });

    // Our Team A player should NOT appear because Team A has a game at the same time
    const aliceInPanel = panel.getByText(aliceFirst);
    await expect(aliceInPanel).not.toBeVisible();
  });

  test("backend rejects assignment of player whose team has a game at the same time", async ({ request }) => {
    // Get the tasks for Team A's game. The seasons endpoint is paginated
    // (fixed page size of 100) and long-lived dev databases accumulate many
    // test seasons, so walk the pages until the new season is found.
    let season: { id: number; name: string } | undefined;
    for (let p = 1; p <= 10 && !season; p++) {
      const seasonsRes = await request.get(`${API}/seasons/?page=${p}`, {
        headers: { Authorization: `Token ${token}` },
      });
      const seasonsData = await seasonsRes.json();
      const seasonsList = Array.isArray(seasonsData)
        ? seasonsData
        : (seasonsData.results ?? []);
      season = seasonsList.find((s: { name: string }) => s.name === seasonName);
    }
    expect(season, "newly imported season should be listed").toBeTruthy();

    const gamesRes = await request.get(`${API}/games/?season=${season.id}`, {
      headers: { Authorization: `Token ${token}` },
    });
    const gamesData = await gamesRes.json();
    const gamesList = Array.isArray(gamesData) ? gamesData : gamesData.results ?? [];
    const teamAGame = gamesList.find((g: { own_team: { name: string } }) => g.own_team.name === teamA);

    const tasksRes = await request.get(`${API}/tasks/?game=${teamAGame.id}`, {
      headers: { Authorization: `Token ${token}` },
    });
    const tasksData = await tasksRes.json();
    const tasksList = Array.isArray(tasksData) ? tasksData : tasksData.results ?? [];
    const task = tasksList[0];

    // Find our Team B player (unique name — no ambiguity with other tests'
    // players). Walk all pages: new players land at the END of the list.
    const playersList = await fetchAllPages<{
      id: number;
      first_name: string;
      last_name: string;
    }>(request, `${API}/players/`, token);
    const bob = playersList.find(
      (p) => p.first_name === bobFirst && p.last_name === "PlayerB",
    );

    // Attempt to assign Bob to Team A's task — should be rejected (endpoint is /assignments/)
    const assignRes = await request.post(`${API}/assignments/`, {
      headers: { Authorization: `Token ${token}` },
      data: { task_id: task.id, player_id: bob.id },
    });

    // Backend must return 400 because Bob's team has a game at the same time
    const responseText = await assignRes.text();
    expect(assignRes.status(), `Expected 400, got: ${responseText.slice(0, 200)}`).toBe(400);
  });
});