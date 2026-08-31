import { test, expect, type Page } from "./fixtures";
import { authenticate, uniqueName } from "./helpers";

const API = "/api";

async function selectSeason(page: Page, seasonName: string): Promise<void> {
  await page.getByTestId("season-dropdown-toggle").click();
  await page.getByTestId("season-dropdown-menu")
    .getByText(seasonName, { exact: true })
    .click();
}

test.describe("Availability", () => {
  test("shows away days with team, opponent, time and unavailable count", async ({
    request,
    page,
  }: {
    request: any;
    page: Page;
  }) => {
    // Unique names per test (see uniqueName): players are matched globally
    // by first+last name, so fixed names like "Ann Away" would be shared rows
    // across parallel tests and a concurrent import could move them.
    const annFirst = uniqueName("Ann");
    const benFirst = uniqueName("Ben");
    const token = await authenticate(request, page, uniqueName("av-"));
    const seasonName = uniqueName("Avail-");
    const teamName = uniqueName("A");
    const homeTeam = uniqueName("Team A");

    const scheduleCsv = [
      "date,time,court,home_team,away_team,game_type",
      `2025-11-03,18:00,1,${homeTeam},${uniqueName("Team B")}`,
      `2025-11-04,19:30,1,${teamName},Rival Club,AWAY`,
    ].join("\n");
    const impRes = await request.post(`${API}/seasons/import_schedule/`, {
      headers: { Authorization: `Token ${token}` },
      data: { season_name: seasonName, csv_text: scheduleCsv },
    });
    expect(impRes.status()).toBe(201);

    const membersCsv = [
      "first_name,last_name,team,is_coach,referee_certification",
      `${annFirst},Away,${teamName},False,F`,
      `${benFirst},Bench,${teamName},True,SENIOR`,
    ].join("\n");
    const memRes = await request.post(`${API}/players/import_members/`, {
      headers: { Authorization: `Token ${token}` },
      data: { csv_text: membersCsv, upsert: true },
    });
    expect(memRes.status()).toBe(201);

    await page.goto("/");
    await selectSeason(page, seasonName);
    await page.getByRole("button", { name: "Availability" }).click();

    await expect(page.getByRole("heading", { name: "Availability" })).toBeVisible();

    // Only the AWAY day is shown — the home game is not.
    // Scope to the block containing both the opponent and its members
    // (CSS modules hash class names, so select structurally).
    const awayGame = page
      .locator("div")
      .filter({ has: page.getByText("vs Rival Club", { exact: true }) })
      .filter({ has: page.getByText(`${benFirst} Bench (C)`) })
      .last();
    await expect(awayGame.getByText(teamName)).toBeVisible();
    // exact: "AWAY" would otherwise also match inside "… unavailable"
    await expect(awayGame.getByText("AWAY", { exact: true })).toBeVisible();
    await expect(awayGame.getByText("vs Rival Club")).toBeVisible();
    await expect(awayGame.getByText("19:30")).toBeVisible();
    await expect(awayGame.getByText("2 unavailable", { exact: true })).toBeVisible();

    // Both members are listed; the coach gets a (C) suffix
    await expect(awayGame.getByText(`${annFirst} Away`)).toBeVisible();
    await expect(awayGame.getByText(`${benFirst} Bench (C)`)).toBeVisible();

    // The home game must NOT appear in availability
    await expect(page.getByText(homeTeam)).toHaveCount(0);
  });

  test("shows the empty state for a season without away games", async ({
    request,
    page,
  }: {
    request: any;
    page: Page;
  }) => {
    const token = await authenticate(request, page, uniqueName("ae-"));
    const seasonName = uniqueName("AvailEmpty-");

    const scheduleCsv = [
      "date,time,court,home_team,away_team",
      `2025-11-03,18:00,1,${uniqueName("Team A")},${uniqueName("Team B")}`,
    ].join("\n");
    const impRes = await request.post(`${API}/seasons/import_schedule/`, {
      headers: { Authorization: `Token ${token}` },
      data: { season_name: seasonName, csv_text: scheduleCsv },
    });
    expect(impRes.status()).toBe(201);

    await page.goto("/");
    await selectSeason(page, seasonName);
    await page.getByRole("button", { name: "Availability" }).click();

    await expect(page.getByRole("heading", { name: "Availability" })).toBeVisible();
    await expect(page.getByText("No away games scheduled for this season.")).toBeVisible();
  });

  test("hides away games from the planner view", async ({
    request,
    page,
  }: {
    request: any;
    page: Page;
  }) => {
    const token = await authenticate(request, page, uniqueName("ap-"));
    const seasonName = uniqueName("AvailPlan-");
    const teamName = uniqueName("P");
    const homeTeam = uniqueName("Team A");

    const scheduleCsv = [
      "date,time,court,home_team,away_team,game_type",
      `2025-11-03,18:00,1,${homeTeam},${uniqueName("Team B")}`,
      `2025-11-04,19:30,1,${teamName},Rival Club,AWAY`,
    ].join("\n");
    const impRes = await request.post(`${API}/seasons/import_schedule/`, {
      headers: { Authorization: `Token ${token}` },
      data: { season_name: seasonName, csv_text: scheduleCsv },
    });
    expect(impRes.status()).toBe(201);

    await page.goto("/");
    await selectSeason(page, seasonName);

    // Home game visible, away game hidden
    await expect(page.getByText(homeTeam)).toBeVisible();
    await expect(page.getByText(`vs Rival Club`)).toHaveCount(0);
  });
});
