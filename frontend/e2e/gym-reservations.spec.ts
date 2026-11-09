import { test, expect } from "./fixtures";
import type { APIRequestContext, Page } from "@playwright/test";
import { authenticate, fetchAllPages, uniqueName } from "./helpers";

const API = "/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function selectSeason(page: Page, name: string) {
  await page.getByTestId("season-dropdown-toggle").click();
  await page.getByTestId("season-dropdown-menu").getByText(name, { exact: true }).click();
}

async function openGymTab(page: Page) {
  await page.getByTestId("planner-tab-gym").click();
  await expect(page.getByRole("heading", { name: "Gym Reservations" })).toBeVisible({ timeout: 10_000 });
}

interface SeasonItem {
  id: number;
  name: string;
}

async function findSeasonId(request: APIRequestContext, token: string, name: string): Promise<number> {
  const seasons = await fetchAllPages<SeasonItem>(request, `${API}/seasons/`, token);
  const match = seasons.find((s) => s.name === name);
  if (!match) throw new Error(`Season "${name}" not found`);
  return match.id;
}

/** Create a reservation directly via the API (for setup in tests that assert UI state). */
async function apiCreateReservation(
  request: APIRequestContext,
  token: string,
  data: { season: number; date: string; start_time: string; end_time: string; note?: string },
): Promise<number> {
  const res = await request.post(`${API}/reservations/`, {
    headers: { Authorization: `Token ${token}` },
    data,
  });
  expect(res.status(), "create reservation should succeed").toBe(201);
  const body = await res.json();
  return body.id as number;
}

async function apiDeleteReservation(request: APIRequestContext, token: string, id: number) {
  const res = await request.delete(`${API}/reservations/${id}/`, {
    headers: { Authorization: `Token ${token}` },
  });
  expect(res.status()).toBe(204);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe("Gym Reservations", () => {
  let token: string;
  let seasonName: string;
  let seasonId: number;
  let teamA: string;
  let teamB: string;

  test.beforeEach(async ({ request, page }) => {
    token = await authenticate(request, page, uniqueName("gr-"));
    seasonName = uniqueName("Gym-");
    teamA = uniqueName("Team A");
    teamB = uniqueName("Team B");

    // One home game on 2025-10-01 at 14:00.
    const scheduleCsv = `date,time,court,home_team,away_team\n2025-10-01,14:00,1,${teamA},${teamB}`;
    const schedRes = await request.post(`${API}/seasons/import_schedule/`, {
      headers: { Authorization: `Token ${token}` },
      data: { season_name: seasonName, csv_text: scheduleCsv },
    });
    expect(schedRes.status()).toBe(201);

    seasonId = await findSeasonId(request, token, seasonName);
  });

  // -------------------------------------------------------------------------
  // 1. Navigation & visibility
  // -------------------------------------------------------------------------

  test("shows the Gym tab next to Schedule and Versions", async ({ page }) => {
    await page.goto("/");
    await selectSeason(page, seasonName);
    await expect(page.getByTestId("planner-tab-schedule")).toBeVisible();
    await expect(page.getByTestId("planner-tab-versions")).toBeVisible();
    await expect(page.getByTestId("planner-tab-gym")).toBeVisible();
    await expect(page.getByTestId("planner-tab-gym")).toHaveAttribute("aria-selected", "false");
  });

  test("opens the Gym panel when clicking the Gym tab", async ({ page }) => {
    await page.goto("/");
    await selectSeason(page, seasonName);
    await page.getByTestId("planner-tab-gym").click();
    await expect(page.getByTestId("planner-tab-gym")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("heading", { name: "Gym Reservations" })).toBeVisible();
  });

  test("switches back to the Schedule tab", async ({ page }) => {
    await page.goto("/");
    await selectSeason(page, seasonName);
    await page.getByTestId("planner-tab-gym").click();
    await expect(page.getByRole("heading", { name: "Gym Reservations" })).toBeVisible();
    await page.getByTestId("planner-tab-schedule").click();
    await expect(page.getByTestId("planner-tab-schedule")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("heading", { name: "Gym Reservations" })).toHaveCount(0);
  });

  test("shows the coverage badge listing uncovered games", async ({ page, request }) => {
    await page.goto("/");
    await selectSeason(page, seasonName);
    const badge = page.getByTestId("gym-coverage-badge");
    await expect(badge).toBeVisible();
    await expect(badge).toContainText("1 game without a gym reservation");
  });

  test("clicking the coverage badge opens the Gym tab", async ({ page }) => {
    await page.goto("/");
    await selectSeason(page, seasonName);
    await page.getByTestId("gym-coverage-badge").click();
    await expect(page.getByTestId("planner-tab-gym")).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("heading", { name: "Gym Reservations" })).toBeVisible();
  });

  test("hides the coverage badge when every home game is covered", async ({ page }) => {
    // Create a reservation that covers the 14:00 game (needs 13:30–16:15).
    await apiCreateReservation(page.request, token, {
      season: seasonId,
      date: "2025-10-01",
      start_time: "13:30:00",
      end_time: "16:15:00",
    });
    await page.goto("/");
    await selectSeason(page, seasonName);
    await expect(page.getByTestId("gym-coverage-badge")).toHaveCount(0);
  });

  // -------------------------------------------------------------------------
  // 2. Viewing reservations (empty state + seeded demo season)
  // -------------------------------------------------------------------------

  test("shows an uncovered timeline when there are games but no reservations", async ({ page }) => {
    await page.goto("/");
    await selectSeason(page, seasonName);
    await openGymTab(page);
    // With 1 home game and no reservation, the day bar shows a red "needed"
    // segment, a summary line, and a quick-add button.
    await expect(page.locator("[class*='seg-needed']").first()).toBeVisible();
    await expect(page.getByText(/game needs a reservation/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Add reservation for this date" })).toBeVisible();
  });

  test.describe("Seeded demo season (read-only)", () => {
    /** Scope to a date-group card within the gym panel by its formatted date text. */
    function dateGroup(page: Page, dateText: RegExp) {
      return page.locator("[class*='gym-panel'] [class*='date-group']").filter({ hasText: dateText });
    }

    test("shows fully covered date with reservation card and surplus", async ({ page }) => {
      await page.goto("/");
      await selectSeason(page, "2025-2026");
      await openGymTab(page);

      // Oct 4: "Full day booking" 12:30–20:00
      const oct4 = dateGroup(page, /4 oktober/);
      await expect(oct4.getByText("12:30–20:00")).toBeVisible();
      await expect(oct4.getByText("Full day booking")).toBeVisible();
      // Surplus tail (19:15–20:00) is reported as returnable
      await expect(oct4.getByText(/returnable/)).toBeVisible();
      await expect(oct4.getByText("Fully covered")).toBeVisible();
    });

    test("shows partly reserved date with both card and warning", async ({ page }) => {
      await page.goto("/");
      await selectSeason(page, "2025-2026");
      await openGymTab(page);

      // Oct 18: morning block 12:30–16:15 + uncovered afternoon games
      const oct18 = dateGroup(page, /18 oktober/);
      await expect(oct18.getByText("12:30–16:15")).toBeVisible();
      await expect(oct18.getByText("Morning block only")).toBeVisible();
      // Uncovered afternoon games render as red segments with a summary + quick add
      await expect(oct18.locator("[class*='seg-needed']").first()).toBeVisible();
      await expect(oct18.getByText(/games need a reservation/)).toBeVisible();
      await expect(oct18.getByText("Add reservation for this date")).toBeVisible();
    });

    test("shows a midday-only reservation with uncovered morning and evening", async ({ page }) => {
      await page.goto("/");
      await selectSeason(page, "2025-2026");
      await openGymTab(page);

      // Oct 11: "Midday block only" 14:00–16:15 covers the midday games;
      // the 13:00 and 17:30 games are left uncovered on both sides.
      const oct11 = dateGroup(page, /11 oktober/);
      await expect(oct11.getByText("14:00–16:15")).toBeVisible();
      await expect(oct11.getByText("Midday block only")).toBeVisible();
      // Covered midday games render green; uncovered morning/evening render red
      await expect(oct11.locator("[class*='seg-covered']").first()).toBeVisible();
      await expect(oct11.locator("[class*='seg-needed']").first()).toBeVisible();
      await expect(oct11.getByText(/games need a reservation/)).toBeVisible();
    });

    test("shows a gap between game windows on the split booking date", async ({ page }) => {
      await page.goto("/");
      await selectSeason(page, "2025-2026");
      await openGymTab(page);

      // Nov 1: "Split booking" 12:30–19:15 with only 13:00 and 17:30 games
      const nov1 = dateGroup(page, /1 november/);
      await expect(nov1.getByText("12:30–19:15")).toBeVisible();
      await expect(nov1.getByText("Split booking (morning + evening)")).toBeVisible();
      // The gap is identified as returnable surplus
      await expect(nov1.getByText(/returnable/)).toBeVisible();
    });

    test("shows a warning card for the date without any reservation", async ({ page }) => {
      await page.goto("/");
      await selectSeason(page, "2025-2026");
      await openGymTab(page);

      // Nov 15 has no reservation (Nov 1 has the gap reservation)
      const nov15 = dateGroup(page, /15 november/);
      await expect(nov15.locator("[class*='seg-needed']").first()).toBeVisible();
      await expect(nov15.getByText(/games need a reservation/)).toBeVisible();
      await expect(nov15.getByText("Add reservation for this date")).toBeVisible();
    });

    test("shows the season coverage summary line", async ({ page, request }) => {
      await page.goto("/");
      await selectSeason(page, "2025-2026");
      await openGymTab(page);

      // Fetch coverage from API to get dynamic counts
      const adminRes = await request.post(`${API}/auth/login/`, { data: { username: "admin", password: "admin" } });
      const adminToken = (await adminRes.json()).token as string;
      const seasons = await fetchAllPages<SeasonItem>(request, `${API}/seasons/`, adminToken);
      const demoSeason = seasons.find((s) => s.name === "2025-2026")!;
      const covRes = await request.get(`${API}/seasons/${demoSeason.id}/gym_coverage/`, {
        headers: { Authorization: `Token ${adminToken}` },
      });
      const coverage = await covRes.json();

      const subtitle = page.locator("p").filter({ hasText: /home games covered/ }).first();
      await expect(subtitle).toContainText(`${coverage.covered_games} of ${coverage.total_home_games} home games covered`);
    });
  });

  // -------------------------------------------------------------------------
  // 3. Creating a reservation
  // -------------------------------------------------------------------------

  test("opens the add modal from the + Add Reservation button", async ({ page }) => {
    await page.goto("/");
    await selectSeason(page, seasonName);
    await openGymTab(page);
    await page.getByRole("button", { name: "+ Add Reservation" }).click();

    const modal = page.locator(".modal");
    await expect(modal).toBeVisible();
    await expect(modal.getByRole("heading", { name: "Add Reservation" })).toBeVisible();
    await expect(page.locator("#res-start")).toHaveValue("09:00");
    await expect(page.locator("#res-end")).toHaveValue("17:00");
  });

  test("creates a reservation through the form", async ({ page }) => {
    await page.goto("/");
    await selectSeason(page, seasonName);
    await openGymTab(page);
    await page.getByRole("button", { name: "+ Add Reservation" }).click();

    await page.locator("#res-date").fill("2025-10-01");
    await page.locator("#res-start").fill("13:30");
    await page.locator("#res-end").fill("16:15");
    await page.locator("#res-note").fill("Test booking");
    // The submit button is the primary button in the modal footer
    await page.locator(".modal").getByRole("button", { name: "Add" }).click();

    // Modal closes, reservation pill appears
    await expect(page.locator(".modal")).toHaveCount(0);
    await expect(page.getByText("13:30–16:15")).toBeVisible();
    await expect(page.getByText("Test booking")).toBeVisible();
  });

  test("pre-fills the date from 'Add reservation for this date'", async ({ page }) => {
    await page.goto("/");
    await selectSeason(page, seasonName);
    await openGymTab(page);
    // The warning card has an "Add reservation for this date" button
    await page.getByRole("button", { name: "Add reservation for this date" }).click();
    await expect(page.locator("#res-date")).toHaveValue("2025-10-01");
  });

  test("cancelling the add modal creates nothing", async ({ page }) => {
    await page.goto("/");
    await selectSeason(page, seasonName);
    await openGymTab(page);
    await page.getByRole("button", { name: "+ Add Reservation" }).click();
    await page.locator("#res-date").fill("2025-10-01");
    await page.locator("#res-start").fill("10:00");
    await page.locator("#res-end").fill("12:00");
    await page.locator(".modal").getByRole("button", { name: "Cancel" }).click();

    await expect(page.locator(".modal")).toHaveCount(0);
    // The day bar still shows an uncovered (red) segment for the game
    await expect(page.locator("[class*='seg-needed']")).toBeVisible();
  });

  test("closes the add modal on Escape", async ({ page }) => {
    await page.goto("/");
    await selectSeason(page, seasonName);
    await openGymTab(page);
    await page.getByRole("button", { name: "+ Add Reservation" }).click();
    await expect(page.locator(".modal")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.locator(".modal")).toHaveCount(0);
  });

  // -------------------------------------------------------------------------
  // 4. Editing a reservation
  // -------------------------------------------------------------------------

  test("opens the edit modal pre-filled with saved values", async ({ page }) => {
    await apiCreateReservation(page.request, token, {
      season: seasonId,
      date: "2025-10-01",
      start_time: "13:00:00",
      end_time: "16:00:00",
      note: "Original",
    });
    await page.goto("/");
    await selectSeason(page, seasonName);
    await openGymTab(page);

    await page.getByTitle("Edit reservation").click();
    const modal = page.locator(".modal");
    await expect(modal.getByRole("heading", { name: "Edit Reservation" })).toBeVisible();
    await expect(page.locator("#res-date")).toHaveValue("2025-10-01");
    await expect(page.locator("#res-start")).toHaveValue("13:00");
    await expect(page.locator("#res-end")).toHaveValue("16:00");
    await expect(page.locator("#res-note")).toHaveValue("Original");
  });

  test("saves edited times and note", async ({ page }) => {
    await apiCreateReservation(page.request, token, {
      season: seasonId,
      date: "2025-10-01",
      start_time: "13:00:00",
      end_time: "16:00:00",
      note: "Before",
    });
    await page.goto("/");
    await selectSeason(page, seasonName);
    await openGymTab(page);

    await page.getByTitle("Edit reservation").click();
    await page.locator("#res-end").fill("17:00");
    await page.locator("#res-note").fill("After");
    await page.getByRole("button", { name: "Save" }).click();

    await expect(page.locator(".modal")).toHaveCount(0);
    await expect(page.getByText("13:00–17:00")).toBeVisible();
    await expect(page.getByText("After")).toBeVisible();
  });

  // -------------------------------------------------------------------------
  // 5. Deleting a reservation
  // -------------------------------------------------------------------------

  test("deletes a reservation after confirmation", async ({ page }) => {
    await apiCreateReservation(page.request, token, {
      season: seasonId,
      date: "2025-10-01",
      start_time: "13:00:00",
      end_time: "16:00:00",
    });
    await page.goto("/");
    await selectSeason(page, seasonName);
    await openGymTab(page);

    // Trash icon opens the Edit modal
    await page.getByTitle("Delete reservation").click();
    await expect(page.locator(".modal")).toBeVisible();
    // Click the "Delete" button in the modal footer to show confirmation
    await page.locator(".modal").getByRole("button", { name: "Delete" }).click();
    // Confirmation appears
    await expect(page.getByText("Delete this reservation?")).toBeVisible();
    // Click the confirm "Delete" button (inside .delete-confirm)
    await page.locator("[class*='delete-confirm']").getByRole("button", { name: "Delete" }).click();

    await expect(page.locator(".modal")).toHaveCount(0);
    // Reservation pill is gone
    await expect(page.getByText("13:00–16:00")).toHaveCount(0);
  });

  test("canceling the delete confirmation keeps the reservation", async ({ page }) => {
    await apiCreateReservation(page.request, token, {
      season: seasonId,
      date: "2025-10-01",
      start_time: "13:00:00",
      end_time: "16:00:00",
    });
    await page.goto("/");
    await selectSeason(page, seasonName);
    await openGymTab(page);

    await page.getByTitle("Delete reservation").click();
    await expect(page.locator(".modal")).toBeVisible();
    await page.locator(".modal").getByRole("button", { name: "Delete" }).click();
    await expect(page.getByText("Delete this reservation?")).toBeVisible();
    // Click Cancel inside the confirm section
    await page.locator("[class*='delete-confirm']").getByRole("button", { name: "Cancel" }).click();

    // Confirm hidden, modal still open, card still present
    await expect(page.getByText("Delete this reservation?")).toHaveCount(0);
    await expect(page.locator(".modal")).toBeVisible();
    // Close modal
    await page.keyboard.press("Escape");
    await expect(page.getByText("13:00–16:00")).toBeVisible();
  });

  // -------------------------------------------------------------------------
  // 6. Coverage badge updates
  // -------------------------------------------------------------------------

  test("badge disappears after adding a covering reservation", async ({ page }) => {
    await page.goto("/");
    await selectSeason(page, seasonName);
    await expect(page.getByTestId("gym-coverage-badge")).toBeVisible();

    // Add a reservation covering the 14:00 game (needs 13:30–16:15)
    await openGymTab(page);
    await page.getByRole("button", { name: "+ Add Reservation" }).click();
    await page.locator("#res-date").fill("2025-10-01");
    await page.locator("#res-start").fill("13:30");
    await page.locator("#res-end").fill("16:15");
    await page.locator(".modal").getByRole("button", { name: "Add" }).click();

    // Badge should disappear (query invalidation refreshes the header)
    await expect(page.getByTestId("gym-coverage-badge")).toHaveCount(0);
  });

  test("badge reappears after deleting the covering reservation", async ({ page }) => {
    await apiCreateReservation(page.request, token, {
      season: seasonId,
      date: "2025-10-01",
      start_time: "13:30:00",
      end_time: "16:15:00",
    });
    await page.goto("/");
    await selectSeason(page, seasonName);
    // No badge initially (covered)
    await expect(page.getByTestId("gym-coverage-badge")).toHaveCount(0);

    // Delete via UI
    await openGymTab(page);
    await page.getByTitle("Delete reservation").click();
    await expect(page.locator(".modal")).toBeVisible();
    await page.locator(".modal").getByRole("button", { name: "Delete" }).click();
    await expect(page.getByText("Delete this reservation?")).toBeVisible();
    await page.locator("[class*='delete-confirm']").getByRole("button", { name: "Delete" }).click();

    // Badge reappears
    await expect(page.getByTestId("gym-coverage-badge")).toBeVisible();
    await expect(page.getByTestId("gym-coverage-badge")).toContainText("1 game");
  });

  // -------------------------------------------------------------------------
  // 7. Edge cases
  // -------------------------------------------------------------------------

  test("rejects a reservation whose end time equals start time", async ({ page }) => {
    await page.goto("/");
    await selectSeason(page, seasonName);
    await openGymTab(page);
    await page.getByRole("button", { name: "+ Add Reservation" }).click();
    await page.locator("#res-date").fill("2025-10-01");
    await page.locator("#res-start").fill("15:00");
    await page.locator("#res-end").fill("15:00");
    await page.locator(".modal").getByRole("button", { name: "Add" }).click();

    // Client-side validation error
    await expect(page.locator(".modal .error")).toContainText("End time must be after start time.");
    // Modal stays open
    await expect(page.locator(".modal")).toBeVisible();
  });

  test("ignores away games in coverage", async ({ page, request }) => {
    // Add an away game to the season
    const awayCsv = `date,time,court,home_team,away_team,game_type\n2025-10-02,14:00,1,${teamA},${teamB},AWAY`;
    const res = await request.post(`${API}/seasons/import_schedule/`, {
      headers: { Authorization: `Token ${token}` },
      data: { season_name: seasonName, csv_text: awayCsv },
    });
    expect(res.status()).toBe(201);

    await page.goto("/");
    await selectSeason(page, seasonName);
    // Only 1 home game → badge says "1 game"
    await expect(page.getByTestId("gym-coverage-badge")).toContainText("1 game without a gym reservation");
  });
});
