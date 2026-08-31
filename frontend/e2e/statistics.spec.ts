import { test, expect, type Page } from "./fixtures";
import { authenticate, fetchAllPages, uniqueName } from "./helpers";

const API = "/api";

interface GameRecord {
  id: number;
  game_type: string;
  [key: string]: unknown;
}
interface PlayerRecord {
  id: number;
  full_name: string;
  team: { name: string };
  [key: string]: unknown;
}

test.describe("Statistics", () => {
  // These tests seed shared state via the API; run serially to avoid
  // collisions on the shared SQLite database.
  test.describe.configure({ mode: "serial" });

  let seasonName: string;

  test.beforeEach(async ({ request, page }) => {
    const token = await authenticate(request, page, uniqueName("st-"));
    seasonName = uniqueName("Stats-");

    // Seed a season. The away-day player (Vido X14-Away) gets assigned to a
    // neutral HOME game on 2025-10-08 — a date where their own team has no home
    // game, so it counts as an away-day (2x) task. We avoid assigning them to
    // their own travelling team's away game (blocked by domain rules).
    const scheduleCsv =
      "date,time,court,home_team,away_team,game_type\n" +
      "2025-10-01,14:00,1,Vido X14-Home,Opponent,HOME\n" +
      "2025-10-08,14:00,1,Vido X14-Neutral,Opponent,HOME";

    const schedRes = await request.post(`${API}/seasons/import_schedule/`, {
      headers: { Authorization: `Token ${token}` },
      data: { season_name: seasonName, csv_text: scheduleCsv },
    });
    expect(schedRes.status(), "import_schedule should succeed").toBe(201);

    // Unique last name so the lookup below finds exactly this player.
    const playerLast = uniqueName("Player");
    const membersCsv =
      "first_name,last_name,team,is_coach,referee_certification\n" +
      `Away,${playerLast},Vido X14-Away,False,NONE`;
    const memRes = await request.post(`${API}/players/import_members/`, {
      headers: { Authorization: `Token ${token}` },
      data: { csv_text: membersCsv, upsert: true },
    });
    expect(memRes.status(), "import_members should succeed").toBe(201);

    // Assign the away-day player to a task on the away game so the leaderboard
    // has an entry with an away-day bonus.
    const seasons = await fetchAllPages<{ id: number; name: string }>(
      request,
      `${API}/seasons/`,
      token,
    );
    // Select the season we just created (the DB may contain other seasons)
    const seasonId = (seasons.find((s) => s.name === seasonName) ?? seasons[0]).id;
    const gamesRes = await request.get(`${API}/games/?season=${seasonId}`, {
      headers: { Authorization: `Token ${token}` },
    });
    const gamesBody = await gamesRes.json();
    const games = (
      Array.isArray(gamesBody) ? gamesBody : gamesBody.results
    ) as GameRecord[];
    const awayGame = games.find((g) => g.date === "2025-10-08")!;
    const tasksRes = await request.get(
      `${API}/games/${awayGame.id}/tasks_with_assignments/`,
      { headers: { Authorization: `Token ${token}` } },
    );
    const tasks = await tasksRes.json();
    // Walk all pages — newly created players land at the END of the list and
    // fall off page 1 once the DB holds more than 100 players.
    const players = await fetchAllPages<PlayerRecord>(
      request,
      `${API}/players/`,
      token,
    );
    const player = players.find(
      (p) => p.team.name === "Vido X14-Away" && p.last_name === playerLast,
    )!;
    // Use a SCORER task — the seeded player has no referee certification
    const scorerTask = (tasks as { id: number; task_type: string }[]).find(
      (t) => t.task_type === "SCORER",
    )!;
    const assignRes = await request.post(
      `${API}/assignments/`,
      {
        headers: { Authorization: `Token ${token}` },
        data: { task_id: scorerTask.id, player_id: player.id },
      },
    );
    expect(assignRes.status(), "assignment should succeed").toBe(201);
  });

  async function openStatistics(page: Page) {
    await page.goto("/");
    await page.getByTestId("season-dropdown-toggle").click();
    await page.getByTestId("season-dropdown-menu").getByText(seasonName, { exact: true }).click();
    await page.getByRole("navigation").getByRole("button", { name: "Statistics" }).click();
  }

  test("shows the away-day bonus column in the leaderboard", async ({ page }: { page: Page }) => {
    await openStatistics(page);

    // The leaderboard table should surface the away-day multiplier column.
    await expect(page.getByRole("columnheader", { name: "Away-day Bonus" })).toBeVisible();
    // The away-day player should show a bonus of "1.0 (1×2)".
    await expect(page.getByText(/1\.0 \(1×2\)/)).toBeVisible();
  });

  test("explains the 2x multiplier", async ({ page }: { page: Page }) => {
    await openStatistics(page);

    await expect(
      page.getByText(/count double \(2×\) toward the effective total/),
    ).toBeVisible();
  });
});
