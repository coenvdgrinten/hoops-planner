import { test, expect } from "./fixtures";
import type { APIRequestContext, Download, Page } from "@playwright/test";
import { authenticate, fetchAllPages, uniqueName } from "./helpers";

const API = "/api";

test.describe("Planner", () => {
  let seasonName: string;
  let token: string;
  let teamA: string;
  let teamB: string;
  let teamC: string;
  let teamD: string;

  test.beforeEach(async ({ request, page }) => {
    // uniqueName: the backend keys teams/players by name globally, so fixed
    // names would collide across parallel workers.
    token = await authenticate(request, page, uniqueName("pl-"));
    seasonName = uniqueName("Planner-");
    teamA = uniqueName("Team A");
    teamB = uniqueName("Team B");
    teamC = uniqueName("Team C");
    teamD = uniqueName("Team D");

    const scheduleCsv =
      `date,time,court,home_team,away_team\n2025-10-01,14:00,1,${teamA},${teamB}\n2025-10-01,14:00,2,${teamC},${teamD}`;

    const membersCsv =
      `first_name,last_name,team,is_coach,referee_certification\n${uniqueName("Alice")},Refsen,${teamA},True,SENIOR\n${uniqueName("Bob")},Player,${teamA},False,\n${uniqueName("Charlie")},Coachsen,${teamC},True,F\n${uniqueName("Diana")},Referee,${teamA},False,F\n${uniqueName("Eve")},Player,${teamC},False,NONE`;

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

  async function selectSeason(page: Page, name: string = seasonName) {
    await page.getByTestId("season-dropdown-toggle").click();
    await page.getByTestId("season-dropdown-menu").getByText(name, { exact: true }).click();
  }

  test("displays games after selecting a season", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);
    await expect(page.getByText(teamA)).toBeVisible();
    await expect(page.getByText(teamB)).toBeVisible();
  });

  test("groups games by date", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);
    await expect(page.getByTestId("date-label").first()).toBeVisible();
  });

  test("shows age badges on game cards", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);
    await expect(page.getByTestId("age-badge").first()).toBeVisible();
  });

  test("shows task chips on game cards", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);
    await expect(page.getByTestId(/^task-chip-\d+$/).first()).toBeVisible({ timeout: 10_000 });
  });

  test("opens assignment panel when clicking a task chip", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);
    await page.getByTestId(/^task-chip-\d+$/).first().click();
    const panel = page.getByTestId("assignment-panel");
    await expect(panel).toBeVisible({ timeout: 10_000 });
  });

  test("shows assigned state after adding a player", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);
    await page.getByTestId(/^task-chip-\d+$/).first().click();
    const panel = page.getByTestId("assignment-panel");
    await expect(panel).toBeVisible({ timeout: 10_000 });

    const addBtn = panel.getByTestId(/^add-candidate-\d+$/).first();
    const addBtnVisible = await addBtn.isVisible();

    if (addBtnVisible) {
      await addBtn.click();
      await panel.getByTestId("assignment-panel-close").click();
      await expect(page.getByTestId(/^task-chip-\d+$/).first()).toHaveClass(/filled/, {
        timeout: 10_000,
      });
    }
  });

  test("removes an assignment through the panel", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);
    const chip = page.getByTestId(/^task-chip-\d+$/).first();
    await chip.click();
    const panel = page.getByTestId("assignment-panel");
    await expect(panel).toBeVisible({ timeout: 10_000 });

    const addBtn = panel.getByTestId(/^add-candidate-\d+$/).first();
    await expect(addBtn).toBeVisible({ timeout: 10_000 });
    await addBtn.click();
    await expect(chip).toHaveClass(/filled/, { timeout: 10_000 });

    await panel.getByTitle("Remove").click();
    await expect(chip).toHaveClass(/unfilled/, { timeout: 10_000 });
    await expect(panel.getByText("No one assigned yet")).toBeVisible();
  });

  test("highlights the game whose task is selected", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    // Each seeded game has 4 task chips (2 refs, scorer, timer)
    const firstChip = page.getByTestId(/^task-chip-\d+$/).first();
    await firstChip.click();
    await expect(page.getByTestId("assignment-panel")).toBeVisible({ timeout: 10_000 });

    const firstCard = firstChip.locator("..").locator("..");
    await expect(firstCard).toHaveClass(/selected/);

    const secondChip = page.getByTestId(/^task-chip-\d+$/).nth(4);
    await secondChip.click();
    const secondCard = secondChip.locator("..").locator("..");
    await expect(secondCard).toHaveClass(/selected/);
    await expect(firstCard).not.toHaveClass(/selected/);
  });

  /** Find a season id by name, walking pages (fixed page size of 100). */
  async function findSeasonId(request: APIRequestContext, name: string): Promise<number> {
    for (let p = 1; p <= 10; p++) {
      const data = await (
        await request.get(`${API}/seasons/?page=${p}`, {
          headers: { Authorization: `Token ${token}` },
        })
      ).json();
      const found = (data.results ?? []).find(
        (s: { name: string }) => s.name === name,
      );
      if (found) return found.id;
    }
    throw new Error(`season ${name} not found`);
  }

  /** Find a player id by exact name (walks all pages — new players land at the end). */
  async function findPlayerId(
    request: APIRequestContext,
    first: string,
    last: string,
  ): Promise<number> {
    const players = await fetchAllPages<{
      id: number;
      first_name: string;
      last_name: string;
    }>(request, `${API}/players/`, token);
    const found = players.find(
      (p) => p.first_name === first && p.last_name === last,
    );
    expect(found, `player ${first} ${last} should exist`).toBeTruthy();
    return found!.id;
  }

  /** Deepest div containing both texts/chips = the game card. */
  function gameCard(page: Page, teamName: string) {
    return page
      .locator("div")
      .filter({ hasText: teamName })
      .filter({ has: page.locator('[data-testid^="task-chip-"]') })
      .last();
  }

  test("shows how much an assignment counts toward the player's total", async ({
    request,
    page,
  }: {
    request: APIRequestContext;
    page: Page;
  }) => {
    // Add a member of a third team (no games of its own on the date).
    const samFirst = uniqueName("Sam");
    const memRes = await request.post(`${API}/players/import_members/`, {
      headers: { Authorization: `Token ${token}` },
      data: {
        csv_text: `first_name,last_name,team,is_coach,referee_certification\n${samFirst},Solo,${uniqueName("ZS")},False,F`,
        upsert: true,
      },
    });
    expect(memRes.status()).toBe(201);

    const seasonId = await findSeasonId(request, seasonName);
    const gamesData = await (
      await request.get(`${API}/games/?season=${seasonId}`, {
        headers: { Authorization: `Token ${token}` },
      })
    ).json();
    const teamAGame = (gamesData.results ?? []).find(
      (g: { own_team: { name: string } }) => g.own_team.name === teamA,
    );
    const tasksData = await (
      await request.get(`${API}/tasks/?game=${teamAGame.id}`, {
        headers: { Authorization: `Token ${token}` },
      })
    ).json();
    const scorerTask = (tasksData.results ?? []).find(
      (t: { task_type: string }) => t.task_type === "SCORER",
    );
    const samId = await findPlayerId(request, samFirst, "Solo");
    const assignRes = await request.post(`${API}/assignments/`, {
      headers: { Authorization: `Token ${token}` },
      data: { task_id: scorerTask.id, player_id: samId },
    });
    expect(assignRes.status(), "assignment should succeed").toBe(201);

    // Sam's team has no game on this date → the task counts double.
    const twa = await (
      await request.get(`${API}/games/${teamAGame.id}/tasks_with_assignments/`, {
        headers: { Authorization: `Token ${token}` },
      })
    ).json();
    const assignment = (twa as { id: number; assignments: { effective_value: number }[] }[])
      .find((t) => t.id === scorerTask.id)!
      .assignments[0];
    expect(assignment.effective_value).toBe(2);

    await page.goto("/");
    await selectSeason(page);
    const chip = gameCard(page, teamA)
      .getByTestId(/^task-chip-\d+$/)
      .filter({ hasText: "SCORER" })
      .first();
    await chip.click();
    const panel = page.getByTestId("assignment-panel");
    await expect(panel).toBeVisible({ timeout: 10_000 });

    const samRow = panel
      .locator("div")
      .filter({ has: page.getByText(`${samFirst} Solo`) })
      .filter({ has: page.getByTestId(/^effective-value-\d+$/) })
      .last();
    const badge = samRow.getByTestId(/^effective-value-\d+$/);
    await expect(badge).toBeVisible();
    await expect(badge).toHaveClass(/away/);
  });

  test("marks own-team-day assignments as counting single", async ({
    request,
    page,
  }: {
    request: APIRequestContext;
    page: Page;
  }) => {
    // Created through the UI (not API) so the import's cache invalidation
    // makes the new games visible without waiting for staleTime expiry.
    const seasonName = uniqueName("EffOwn-");
    await page.goto("/");
    await page.getByTestId("season-dropdown-toggle").click();
    await page.getByText("＋ New season").click();
    await page.getByLabel("New season name").fill(seasonName);
    await page.getByRole("button", { name: "Create" }).click();
    await expect(page.getByTestId("season-dropdown-value")).toHaveText(seasonName);

    await page.getByRole("button", { name: "Import Schedule" }).click();
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible();
    await modal.getByLabel("Season name:").fill(seasonName);
    const teamZA = uniqueName("ZA");
    const teamZB = uniqueName("ZB");
    await modal.locator("textarea").fill(
      [
        "date,time,court,home_team,away_team",
        `2025-11-10,18:00,1,${teamZA},Rival Club`,
        `2025-11-10,19:30,1,${teamZB},Rival Two`,
      ].join("\n"),
    );
    await modal.getByRole("button", { name: "Import Schedule" }).click();
    await expect(modal).not.toBeVisible();

    const kimFirst = uniqueName("Kim");
    const memRes = await request.post(`${API}/players/import_members/`, {
      headers: { Authorization: `Token ${token}` },
      data: {
        csv_text: `first_name,last_name,team,is_coach,referee_certification\n${kimFirst},Keeper,${teamZA},False,F`,
        upsert: true,
      },
    });
    expect(memRes.status()).toBe(201);

    const seasonId = await findSeasonId(request, seasonName);
    const gamesData = await (
      await request.get(`${API}/games/?season=${seasonId}`, {
        headers: { Authorization: `Token ${token}` },
      })
    ).json();
    const zbGame = (gamesData.results ?? []).find(
      (g: { own_team: { name: string } }) => g.own_team.name === teamZB,
    );
    const tasksData = await (
      await request.get(`${API}/tasks/?game=${zbGame.id}`, {
        headers: { Authorization: `Token ${token}` },
      })
    ).json();
    const scorerTask = (tasksData.results ?? []).find(
      (t: { task_type: string }) => t.task_type === "SCORER",
    );
    const kimId = await findPlayerId(request, kimFirst, "Keeper");

    const chip = gameCard(page, teamZB)
      .getByTestId(/^task-chip-\d+$/)
      .filter({ hasText: "SCORER" })
      .first();
    await expect(chip).toBeVisible({ timeout: 10_000 });
    await chip.click();
    const panel = page.getByTestId("assignment-panel");
    await expect(panel).toBeVisible({ timeout: 10_000 });

    // Assigned through the UI so the mutation invalidates the task cache.
    const searchBox = panel.getByLabel("Search member or team");
    await searchBox.fill(`${kimFirst} Keeper`);
    const addBtn = panel.getByTestId(`add-candidate-${kimId}`);
    await expect(addBtn).toBeVisible({ timeout: 10_000 });
    await addBtn.click();

    // Kim's team plays on this date → the task counts single (+1, not +2).
    const assignedBadge = panel.getByTestId(/^effective-value-\d+$/).first();
    await expect(assignedBadge).toBeVisible({ timeout: 10_000 });
    await expect(assignedBadge).toHaveText("+1");
    await expect(assignedBadge).not.toHaveClass(/away/);

    const twa = await (
      await request.get(`${API}/games/${zbGame.id}/tasks_with_assignments/`, {
        headers: { Authorization: `Token ${token}` },
      })
    ).json();
    const assignment = (twa as { id: number; assignments: { effective_value: number }[] }[])
      .find((t) => t.id === scorerTask.id)!
      .assignments[0];
    expect(assignment.effective_value).toBe(1);
  });

  test("exports the schedule as CSV", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    await page.getByTestId("export-csv-btn").click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 10_000 });
    const downloadPromise = page.waitForEvent("download");
    await dialog.getByTestId("pdf-warning-export-btn").click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe(`schedule_${seasonName}.csv`);

    const rows = await readDownloadedCsvRows(download);
    expect(rows.join("\n")).toContain(teamA);
  });

  test("warns about open tasks before exporting PDF", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    // Wait for stats to load — the warning depends on the open-task count.
    await expect(page.getByTestId("fill-rate-bar")).toBeVisible();

    await page.getByTestId("export-pdf-btn").click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 10_000 });
    await expect(dialog.getByText(/unplanned task/)).toBeVisible();
    await expect(page.getByTestId("pdf-warning-list")).toBeVisible();

    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).not.toBeVisible();
  });

  test("exports the schedule as PDF", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    await page.getByTestId("export-pdf-btn").click();
    const dialog = page.getByRole("dialog");
    if (await dialog.isVisible().catch(() => false)) {
      const downloadPromise = page.waitForEvent("download");
      await dialog.getByTestId("pdf-warning-export-btn").click();
      const download = await downloadPromise;
      expect(download.suggestedFilename()).toBe(`schedule_${seasonName}.pdf`);
      const buf = await download.createReadStream().then(readStream);
      expect(buf).toContain("%PDF");
      return;
    }

    const downloadPromise = page.waitForEvent("download");
    await page.getByTestId("export-pdf-btn").click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe(`schedule_${seasonName}.pdf`);
    const buf = await download.createReadStream().then(readStream);
    expect(buf).toContain("%PDF");
  });

  test("exports the schedule as calendar (.ics)", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    const downloadPromise = page.waitForEvent("download");
    await page.getByTestId("export-ics-btn").click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe(`schedule_${seasonName}.ics`);

    const ics = await readStream(await download.createReadStream());
    expect(ics).toContain("BEGIN:VCALENDAR");
    expect(ics).toContain("BEGIN:VEVENT");
    expect(ics).toContain("END:VCALENDAR");
    expect(ics).toContain(teamA);
    expect(ics).toContain(teamB);
  });

  /** Import an extra second-half game into the seeded season. */
  async function seedSecondHalfGame(request: APIRequestContext) {
    const res = await request.post(`${API}/seasons/import_schedule/`, {
      headers: { Authorization: `Token ${token}` },
      data: {
        season_name: seasonName,
        csv_text: `date,time,court,home_team,away_team,half\n2026-01-10,14:00,1,${teamA},${teamB},2`,
      },
    });
    expect(res.status(), "second-half import should succeed").toBe(201);
  }

  /** Read a downloaded file's full text content. */
  async function readStream(stream: AsyncIterable<Uint8Array | string>): Promise<string> {
    let text = "";
    for await (const chunk of stream) {
      text += chunk.toString();
    }
    return text;
  }

  /** Read a downloaded CSV and return its data rows (header stripped). */
  async function readDownloadedCsvRows(download: Download): Promise<string[]> {
    const csv = await readStream(await download.createReadStream());
    return csv.trim().split("\n").slice(1);
  }

  test("whole season remains the default export scope", async ({
    page,
    request,
  }) => {
    await seedSecondHalfGame(request);
    await page.goto("/");
    await selectSeason(page);

    await page.getByTestId("export-csv-btn").click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 10_000 });
    // No interaction → the "Whole season" radio is checked by default.
    await expect(dialog.getByTestId("export-scope-full")).toBeChecked();

    const downloadPromise = page.waitForEvent("download");
    await dialog.getByTestId("pdf-warning-export-btn").click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe(`schedule_${seasonName}.csv`);

    const rows = await readDownloadedCsvRows(download);
    const halves = rows.map((r) => r.split(",")[4]);
    expect(halves).toContain("1");
    expect(halves).toContain("2");
  });

  test("exports only the first half as CSV", async ({ page, request }) => {
    await seedSecondHalfGame(request);
    await page.goto("/");
    await selectSeason(page);

    await page.getByTestId("export-csv-btn").click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 10_000 });
    await dialog.getByTestId("export-scope-first-half").check();

    const downloadPromise = page.waitForEvent("download");
    await dialog.getByTestId("pdf-warning-export-btn").click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe(`schedule_${seasonName}.csv`);

    const rows = await readDownloadedCsvRows(download);
    expect(rows.length).toBeGreaterThan(0);
    // Every row's half column (index 4) is "1".
    for (const row of rows) {
      expect(row.split(",")[4]).toBe("1");
    }
  });

  test("exports only the second half as CSV", async ({ page, request }) => {
    await seedSecondHalfGame(request);
    await page.goto("/");
    await selectSeason(page);

    await page.getByTestId("export-csv-btn").click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 10_000 });
    await dialog.getByTestId("export-scope-second-half").check();

    const downloadPromise = page.waitForEvent("download");
    await dialog.getByTestId("pdf-warning-export-btn").click();
    const download = await downloadPromise;

    const rows = await readDownloadedCsvRows(download);
    expect(rows.length).toBeGreaterThan(0);
    for (const row of rows) {
      expect(row.split(",")[4]).toBe("2");
    }
  });

  test("exports a custom selection of games", async ({ page, request }) => {
    await seedSecondHalfGame(request);
    await page.goto("/");
    await selectSeason(page);

    // Resolve the season id and pick two games with distinct dates.
    // (DRF pagination wraps list responses in {count, …, results}.)
    const authHeaders = { Authorization: `Token ${token}` };
    const seasonsPage = await (
      await request.get(`${API}/seasons/`, { headers: authHeaders })
    ).json();
    const seasonId = seasonsPage.results.find(
      (s: { name: string }) => s.name === seasonName,
    ).id;
    const gamesPage = await (
      await request.get(`${API}/games/?season=${seasonId}`, {
        headers: authHeaders,
      })
    ).json();
    const games = Array.isArray(gamesPage) ? gamesPage : gamesPage.results;
    const picked = [games[0], games[games.length - 1]];
    const pickedDates = new Set(picked.map((g: { date: string }) => g.date));

    await page.getByTestId("export-csv-btn").click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 10_000 });
    await dialog.getByTestId("export-scope-custom").check();
    const picker = dialog.getByTestId("game-picker");
    await expect(picker).toBeVisible();
    // The export button stays disabled until at least one game is ticked.
    await expect(dialog.getByTestId("pdf-warning-export-btn")).toBeDisabled();
    for (const g of picked) {
      await picker.getByTestId(`game-picker-${g.id}`).check();
    }
    await expect(dialog.getByTestId("pdf-warning-export-btn")).toBeEnabled();

    const downloadPromise = page.waitForEvent("download");
    await dialog.getByTestId("pdf-warning-export-btn").click();
    const download = await downloadPromise;

    const rows = await readDownloadedCsvRows(download);
    expect(rows.length).toBeGreaterThan(0);
    const exportedDates = new Set(rows.map((r) => r.split(",")[0]));
    expect(exportedDates).toEqual(pickedDates);
  });

  test("shows the full-season statistics checkbox only for scoped PDF exports", async ({
    page,
  }) => {
    await page.goto("/");
    await selectSeason(page);

    // PDF dialog, whole season (default): hidden.
    await page.getByTestId("export-pdf-btn").click();
    let dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 10_000 });
    await expect(dialog.getByTestId("full-season-stats-checkbox")).toHaveCount(0);

    // Select a half → visible.
    await dialog.getByTestId("export-scope-first-half").check();
    await expect(dialog.getByTestId("full-season-stats-checkbox")).toBeVisible();

    // CSV dialog with a half selected → still hidden (CSV has no summaries).
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await page.getByTestId("export-csv-btn").click();
    dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await dialog.getByTestId("export-scope-first-half").check();
    await expect(dialog.getByTestId("full-season-stats-checkbox")).toHaveCount(0);
  });
});
