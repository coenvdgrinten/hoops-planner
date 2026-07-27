import { test, expect, type Page } from "@playwright/test";
import { authenticate } from "./helpers";

const API = "/api";

test.describe("Eligibility - same time conflict", () => {
  let seasonName: string;
  let token: string;

  test.beforeEach(async ({ request, page }) => {
    seasonName = `Elig-${Date.now()}`;
    token = await authenticate(request, page, seasonName);

    // Two teams with HOME games at the exact same time
    const scheduleCsv =
      "date,time,court,home_team,away_team\n" +
      "2025-10-01,14:00,1,Team A,Opponent A\n" +
      "2025-10-01,14:00,2,Team B,Opponent B";

    // Players on Team A and Team B
    const membersCsv =
      "first_name,last_name,team,is_coach,referee_certification\n" +
      "Alice,PlayerA,Team A,False,F\n" +
      "Bob,PlayerB,Team B,False,F\n" +
      "Charlie,Other,Team C,False,F";

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

    // Click on a task chip for Team A's game (first game card)
    const teamACard = page.getByText("Team A").first();
    await expect(teamACard).toBeVisible({ timeout: 10_000 });

    // Find the task chips in Team A's game card
    const taskChips = page.getByTestId(/^task-chip-\d+$/);
    await expect(taskChips.first()).toBeVisible({ timeout: 10_000 });

    // Click the first task chip to open assignment panel
    await taskChips.first().click();

    const panel = page.getByTestId("assignment-panel");
    await expect(panel).toBeVisible({ timeout: 10_000 });

    // Bob (Team B) should NOT appear because Team B has a game at the same time
    const bobInPanel = panel.getByText("Bob");
    await expect(bobInPanel).not.toBeVisible();

    // Alice (Team A) should also NOT appear because it's their own team's game
    const aliceInPanel = panel.getByText("Alice");
    await expect(aliceInPanel).not.toBeVisible();
  });

  test("players from Team A should NOT be eligible for Team B tasks when both games are at same time", async ({ page }) => {
    await page.goto("/");
    await selectSeason(page);

    // Find Team B's game card
    const teamBCard = page.getByText("Team B").first();
    await expect(teamBCard).toBeVisible({ timeout: 10_000 });

    // Get all task chips and find ones in Team B's card
    const taskChips = page.getByTestId(/^task-chip-\d+$/);
    await expect(taskChips.first()).toBeVisible({ timeout: 10_000 });

    // Click a task chip (any task chip should work for this test)
    await taskChips.nth(1).click();

    const panel = page.getByTestId("assignment-panel");
    await expect(panel).toBeVisible({ timeout: 10_000 });

    // Alice (Team A) should NOT appear because Team A has a game at the same time
    const aliceInPanel = panel.getByText("Alice");
    await expect(aliceInPanel).not.toBeVisible();
  });

  test("backend rejects assignment of player whose team has a game at the same time", async ({ request }) => {
    // Get the tasks for Team A's game
    const seasonsRes = await request.get(`${API}/seasons/`, {
      headers: { Authorization: `Token ${token}` },
    });
    const seasonsData = await seasonsRes.json();
    const seasonsList = Array.isArray(seasonsData) ? seasonsData : seasonsData.results ?? [];
    const season = seasonsList.find((s: { name: string }) => s.name === seasonName);

    const gamesRes = await request.get(`${API}/games/?season=${season.id}`, {
      headers: { Authorization: `Token ${token}` },
    });
    const gamesData = await gamesRes.json();
    const gamesList = Array.isArray(gamesData) ? gamesData : gamesData.results ?? [];
    const teamAGame = gamesList.find((g: { home_team: { name: string } }) => g.home_team.name === "Team A");

    const tasksRes = await request.get(`${API}/tasks/?game=${teamAGame.id}`, {
      headers: { Authorization: `Token ${token}` },
    });
    const tasksData = await tasksRes.json();
    const tasksList = Array.isArray(tasksData) ? tasksData : tasksData.results ?? [];
    const task = tasksList[0];

    // Find Bob (Team B player)
    const playersRes = await request.get(`${API}/players/`, {
      headers: { Authorization: `Token ${token}` },
    });
    const playersData = await playersRes.json();
    const playersList = Array.isArray(playersData) ? playersData : playersData.results ?? [];
    const bob = playersList.find((p: { first_name: string }) => p.first_name === "Bob");

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