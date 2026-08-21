import { test, expect, type Page } from "@playwright/test";
import { authenticate } from "./helpers";

const API = "/api";

test.describe("Planner", () => {
  let seasonName: string;
  let token: string;

  test.beforeEach(async ({ request, page }) => {
    token = await authenticate(request, page, `pl-${Date.now()}`);
    seasonName = `Planner-${Date.now()}`;

    // Seed data via API before each test
    const scheduleCsv =
      "date,time,court,home_team,away_team\n2025-10-01,14:00,1,Team A,Team B\n2025-10-01,14:00,2,Team C,Team D";

    const membersCsv =
      "first_name,last_name,team,is_coach,referee_certification\nAlice,Refsen,Team A,True,SENIOR\nBob,Player,Team A,False,\nCharlie,Coachsen,Team C,True,F\nDiana,Referee,Team A,False,F\nEve,Player,Team C,False,NONE";

    // Import schedule (creates season automatically)
    const schedRes = await request.post(`${API}/seasons/import_schedule/`, {
      headers: { Authorization: `Token ${token}` },
      data: { season_name: seasonName, csv_text: scheduleCsv },
    });
    expect(schedRes.status(), "import_schedule should succeed").toBe(201);

    // Import members
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

    // Games should appear
    await expect(page.getByText("Team A")).toBeVisible();
    await expect(page.getByText("Team B")).toBeVisible();
  });

  test("groups games by date", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    // Date group label should be visible
    await expect(page.getByTestId("date-label").first()).toBeVisible();
  });

  test("shows age badges on game cards", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    // Age badges should be visible
    await expect(page.getByTestId("age-badge").first()).toBeVisible();
  });

  test("shows task chips on game cards", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    // Task chips should appear
    await expect(page.getByTestId(/^task-chip-\d+$/).first()).toBeVisible({ timeout: 10_000 });
  });

  test("opens assignment panel when clicking a task chip", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    // Click on a task chip
    await page.getByTestId(/^task-chip-\d+$/).first().click();

    // Assignment panel should appear
    const panel = page.getByTestId("assignment-panel");
    await expect(panel).toBeVisible({ timeout: 10_000 });
  });

  test("shows assigned state after adding a player", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    // Click on a task chip to open panel
    await page.getByTestId(/^task-chip-\d+$/).first().click();
    const panel = page.getByTestId("assignment-panel");
    await expect(panel).toBeVisible({ timeout: 10_000 });

    // Find a candidate to add
    const addBtn = panel.getByTestId(/^add-candidate-\d+$/).first();
    const addBtnVisible = await addBtn.isVisible();

    if (addBtnVisible) {
      await addBtn.click();

      // Close panel and check for filled state
      await panel.getByTestId("assignment-panel-close").click();

      // The game card should show assigned state
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

    // Assign the first suggested candidate
    const addBtn = panel.getByTestId(/^add-candidate-\d+$/).first();
    await expect(addBtn).toBeVisible({ timeout: 10_000 });
    await addBtn.click();
    await expect(chip).toHaveClass(/filled/, { timeout: 10_000 });

    // Remove the assignment again
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

    // The card containing the clicked chip is highlighted
    const firstCard = firstChip.locator("..").locator("..");
    await expect(firstCard).toHaveClass(/selected/);

    // Selecting a task on the other game moves the highlight
    const secondChip = page.getByTestId(/^task-chip-\d+$/).nth(4);
    await secondChip.click();
    const secondCard = secondChip.locator("..").locator("..");
    await expect(secondCard).toHaveClass(/selected/);
    await expect(firstCard).not.toHaveClass(/selected/);
  });

  /** Find a season id by name, walking pages (fixed page size of 100). */
  async function findSeasonId(request: any, name: string): Promise<number> {
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

  /** Find a player id by exact name. */
  async function findPlayerId(
    request: any,
    first: string,
    last: string,
  ): Promise<number> {
    const data = await (
      await request.get(`${API}/players/`, {
        headers: { Authorization: `Token ${token}` },
      })
    ).json();
    const found = (data.results ?? []).find(
      (p: { first_name: string; last_name: string }) =>
        p.first_name === first && p.last_name === last,
    );
    expect(found, `player ${first} ${last} should exist`).toBeTruthy();
    return found.id;
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
    request: any;
    page: Page;
  }) => {
    // Add a member of a third team (no games of its own on the date).
    // Unique name per run: fixed names collide with other runs' players
    // who share the seeded 14:00 slot ("already assigned at this time").
    const ts = Date.now();
    const samFirst = `Sam${ts}`;
    const memRes = await request.post(`${API}/players/import_members/`, {
      headers: { Authorization: `Token ${token}` },
      data: {
        csv_text: `first_name,last_name,team,is_coach,referee_certification\n${samFirst},Solo,ZS${ts},False,F`,
        upsert: true,
      },
    });
    expect(memRes.status()).toBe(201);

    // Assign Sam to Team A's scorer task via the API
    const seasonId = await findSeasonId(request, seasonName);
    const gamesData = await (
      await request.get(`${API}/games/?season=${seasonId}`, {
        headers: { Authorization: `Token ${token}` },
      })
    ).json();
    const teamAGame = (gamesData.results ?? []).find(
      (g: { own_team: { name: string } }) => g.own_team.name === "Team A",
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

    // Sam's team has no game on this date → the task counts double
    const twa = await (
      await request.get(`${API}/games/${teamAGame.id}/tasks_with_assignments/`, {
        headers: { Authorization: `Token ${token}` },
      })
    ).json();
    const assignment = (twa as { id: number; assignments: { effective_value: number }[] })
      .find((t) => t.id === scorerTask.id)!
      .assignments[0];
    expect(assignment.effective_value).toBe(2);

    // The panel shows the highlighted +2× badge next to his name
    await page.goto("/");
    await selectSeason(page);
    const chip = gameCard(page, "Team A")
      .getByTestId(/^task-chip-\d+$/)
      .filter({ hasText: "SCORER" })
      .first();
    await chip.click();
    const panel = page.getByTestId("assignment-panel");
    await expect(panel).toBeVisible({ timeout: 10_000 });

    // The assigned-player row contains both the name and the badge
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
    request: any;
    page: Page;
  }) => {
    // Create a fresh season through the UI (auto-selected afterwards, so no
    // pagination issues), then seed two home games at different times.
    const ts = Date.now();
    const seasonName = `EffOwn-${ts}`;
    await page.goto("/");
    await page.getByTestId("season-dropdown-toggle").click();
    await page.getByText("＋ New season").click();
    await page.getByPlaceholder("e.g. 2025-2026").fill(seasonName);
    await page.getByRole("button", { name: "Create" }).click();
    await expect(page.getByTestId("season-dropdown-value")).toHaveText(seasonName);

    // Import the schedule through the UI: its onSuccess invalidates the
    // ["games"] query, so the Planner picks up the new games. An API-only
    // import would sit behind the 10s staleTime and the Planner would keep
    // showing the cached (empty) list.
    await page.getByRole("button", { name: "Import Schedule" }).click();
    const modal = page.getByRole("dialog");
    await expect(modal).toBeVisible();
    await modal.getByPlaceholder("e.g. 2025-2026").fill(seasonName);
    await modal.locator("textarea").fill(
      [
        "date,time,court,home_team,away_team",
        `2025-11-10,18:00,1,ZA${ts},Rival Club`,
        `2025-11-10,19:30,1,ZB${ts},Rival Two`,
      ].join("\n"),
    );
    await modal.getByRole("button", { name: "Import Schedule" }).click();
    await expect(modal).not.toBeVisible();

    const kimFirst = `Kim${ts}`;
    const memRes = await request.post(`${API}/players/import_members/`, {
      headers: { Authorization: `Token ${token}` },
      data: {
        csv_text: `first_name,last_name,team,is_coach,referee_certification\n${kimFirst},Keeper,ZA${ts},False,F`,
        upsert: true,
      },
    });
    expect(memRes.status()).toBe(201);

    // Locate the ZB game and its scorer task (used for the server-side
    // check at the end).
    const seasonId = await findSeasonId(request, seasonName);
    const gamesData = await (
      await request.get(`${API}/games/?season=${seasonId}`, {
        headers: { Authorization: `Token ${token}` },
      })
    ).json();
    const zbGame = (gamesData.results ?? []).find(
      (g: { own_team: { name: string } }) => g.own_team.name === `ZB${ts}`,
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

    // The UI import invalidated the game list, so the imported games are
    // visible in the Planner.
    const chip = gameCard(page, `ZB${ts}`)
      .getByTestId(/^task-chip-\d+$/)
      .filter({ hasText: "SCORER" })
      .first();
    await expect(chip).toBeVisible({ timeout: 10_000 });
    await chip.click();
    const panel = page.getByTestId("assignment-panel");
    await expect(panel).toBeVisible({ timeout: 10_000 });

    // Assign Kim through the UI — her team ZA is not involved in this game,
    // so she is eligible. An API-only assignment would sit behind the 10s
    // staleTime and the panel would keep showing the cached (empty) list;
    // the UI mutation invalidates the task cache instead. Searching by name
    // puts her at the top of the Suggested list.
    const searchBox = panel.getByPlaceholder("Search member or team...");
    await searchBox.fill(`${kimFirst} Keeper`);
    const addBtn = panel.getByTestId(`add-candidate-${kimId}`);
    await expect(addBtn).toBeVisible({ timeout: 10_000 });
    await addBtn.click();

    // The Assigned section now shows a plain +1 badge next to her name.
    // Kim is the only assignment on this task, so the panel has exactly one
    // effective-value badge.
    const assignedBadge = panel.getByTestId(/^effective-value-\d+$/).first();
    await expect(assignedBadge).toBeVisible({ timeout: 10_000 });
    await expect(assignedBadge).toHaveText("+1");
    await expect(assignedBadge).not.toHaveClass(/away/);

    // Kim's team plays on this date (at 18:00) → the task counts single.
    // Verify server-side that the assignment carries effective_value 1.
    const twa = await (
      await request.get(`${API}/games/${zbGame.id}/tasks_with_assignments/`, {
        headers: { Authorization: `Token ${token}` },
      })
    ).json();
    const assignment = (twa as { id: number; assignments: { effective_value: number }[] })
      .find((t) => t.id === scorerTask.id)!
      .assignments[0];
    expect(assignment.effective_value).toBe(1);
  });

  test("exports the schedule as CSV", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    const downloadPromise = page.waitForEvent("download");
    await page.getByTestId("export-csv-btn").click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe(`schedule_${seasonName}.csv`);

    const stream = await download.createReadStream();
    let csv = "";
    for await (const chunk of stream) {
      csv += chunk.toString();
    }
    expect(csv).toContain("date,time,court");
    expect(csv).toContain("Team A");
  });

  test("warns about open tasks before exporting PDF", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    // Seeded games have unassigned tasks, so clicking Export PDF should show
    // the warning modal instead of downloading immediately.
    await page.getByTestId("export-pdf-btn").click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible({ timeout: 10_000 });
    await expect(dialog.getByText(/unplanned task/)).toBeVisible();
    await expect(page.getByTestId("pdf-warning-list")).toBeVisible();

    // Cancelling closes the modal without downloading.
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).not.toBeVisible();
  });

  test("exports the schedule as PDF", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    await page.getByTestId("export-pdf-btn").click();

    // Open tasks exist → confirm through the warning modal first.
    const dialog = page.getByRole("dialog");
    if (await dialog.isVisible().catch(() => false)) {
      const downloadPromise = page.waitForEvent("download");
      await dialog.getByTestId("pdf-warning-export-btn").click();
      const download = await downloadPromise;

      expect(download.suggestedFilename()).toBe(`schedule_${seasonName}.pdf`);

      const stream = await download.createReadStream();
      let pdf = "";
      for await (const chunk of stream) {
        pdf += chunk.toString();
      }
      expect(pdf).toContain("%PDF");
      return;
    }

    const downloadPromise = page.waitForEvent("download");
    await page.getByTestId("export-pdf-btn").click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe(`schedule_${seasonName}.pdf`);

    const stream = await download.createReadStream();
    let pdf = "";
    for await (const chunk of stream) {
      pdf += chunk.toString();
    }
    expect(pdf).toContain("%PDF");
  });

  test("exports the schedule as calendar (.ics)", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await selectSeason(page);

    const downloadPromise = page.waitForEvent("download");
    await page.getByTestId("export-ics-btn").click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe(`schedule_${seasonName}.ics`);

    const stream = await download.createReadStream();
    let ics = "";
    for await (const chunk of stream) {
      ics += chunk.toString();
    }
    expect(ics).toContain("BEGIN:VCALENDAR");
    expect(ics).toContain("BEGIN:VEVENT");
    expect(ics).toContain("END:VCALENDAR");
    expect(ics).toContain("Team A");
    expect(ics).toContain("Team B");
  });
});
