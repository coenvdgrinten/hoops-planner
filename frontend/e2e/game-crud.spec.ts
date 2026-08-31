import { test, expect, type Page } from "./fixtures";
import { authenticate, uniqueName } from "./helpers";

const API = "/api";

async function selectSeason(page: Page, seasonName: string): Promise<void> {
  await page.getByTestId("season-dropdown-toggle").click();
  await page.getByTestId("season-dropdown-menu")
    .getByText(seasonName, { exact: true })
    .click();
}

/** Seed a season with one home game and a uniquely named team. */
async function seedSeason(
  request: any,
  token: string,
  prefix: string,
): Promise<{ seasonName: string; teamName: string }> {
  const seasonName = uniqueName(prefix);
  const teamName = uniqueName("G");
  const scheduleCsv = [
    "date,time,court,home_team,away_team",
    `2025-10-01,14:00,1,${teamName},Seed Opp`,
  ].join("\n");
  const res = await request.post(`${API}/seasons/import_schedule/`, {
    headers: { Authorization: `Token ${token}` },
    data: { season_name: seasonName, csv_text: scheduleCsv },
  });
  expect(res.status()).toBe(201);
  return { seasonName, teamName };
}

/** Deepest div containing the opponent text AND task chips = the game card. */
function gameCard(page: Page, opponent: string) {
  return page
    .locator("div")
    .filter({ hasText: opponent })
    .filter({ has: page.locator('[data-testid^="task-chip-"]') })
    .last();
}

test.describe("Game CRUD", () => {
  test("creates a game through the Add Game modal", async ({
    request,
    page,
  }: {
    request: any;
    page: Page;
  }) => {
    const token = await authenticate(request, page, uniqueName("gc-"));
    const { seasonName, teamName } = await seedSeason(request, token, "GC");

    await page.goto("/");
    await selectSeason(page, seasonName);
    await expect(page.getByText(teamName)).toBeVisible();

    await page.getByRole("button", { name: "+ Add Game" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("heading", { name: "Add Game" })).toBeVisible();

    // Field order in create mode: Game Type, Own Team, Date, Time, Court, Location, Half, Opponent
    const selects = dialog.getByRole("combobox");
    await selects.nth(1).selectOption({ label: teamName });
    await dialog.locator('input[type="date"]').fill("2025-12-01");
    await dialog.locator('input[type="time"]').fill("10:00");
    await selects.nth(2).selectOption({ label: "Court 2" });
    const textInputs = dialog.locator('input[type="text"]');
    await textInputs.nth(1).fill("Brand New Opp");

    await dialog.getByRole("button", { name: "Create" }).click();

    // The new card appears with auto-created task slots
    await expect(page.getByText("Brand New Opp", { exact: true })).toBeVisible();
    const card = gameCard(page, "Brand New Opp");
    await expect(card.getByText(teamName)).toBeVisible();
    await expect(card.locator('[data-testid^="task-chip-"]')).not.toHaveCount(0);
  });

  test("edits a game through the Edit Game modal", async ({
    request,
    page,
  }: {
    request: any;
    page: Page;
  }) => {
    const token = await authenticate(request, page, uniqueName("ge-"));
    const { seasonName } = await seedSeason(request, token, "GE");

    await page.goto("/");
    await selectSeason(page, seasonName);
    await expect(page.getByText("Seed Opp", { exact: true })).toBeVisible();

    // The edit button sits in the card header (a sibling of the chip row)
    await page
      .locator("main")
      .filter({ hasText: "Seed Opp" })
      .last()
      .getByTitle("Edit game")
      .click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("heading", { name: "Edit Game" })).toBeVisible();

    // Change only the opponent (last text input in edit mode)
    await dialog.locator('input[type="text"]').last().fill("Renamed Opp");
    await dialog.getByRole("button", { name: "Save" }).click();

    await expect(page.getByText("Renamed Opp", { exact: true })).toBeVisible();
    await expect(page.getByText("Seed Opp", { exact: true })).toHaveCount(0);
  });

  test("deletes a game with confirmation", async ({
    request,
    page,
  }: {
    request: any;
    page: Page;
  }) => {
    const token = await authenticate(request, page, uniqueName("gd-"));
    const { seasonName, teamName } = await seedSeason(request, token, "GD");

    await page.goto("/");
    await selectSeason(page, seasonName);
    await expect(page.getByText("Seed Opp", { exact: true })).toBeVisible();

    await page
      .locator("main")
      .filter({ hasText: "Seed Opp" })
      .last()
      .getByTitle("Edit game")
      .click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("button", { name: "Delete" }).click();
    await expect(dialog.getByText("Really delete?")).toBeVisible();
    await dialog.getByRole("button", { name: "Yes" }).click();

    // Card is gone; the season now has no games
    await expect(page.getByText("Seed Opp", { exact: true })).toHaveCount(0);
    await expect(page.locator('[data-testid^="task-chip-"]')).toHaveCount(0);
  });

  test("cancelling the edit modal leaves the game unchanged", async ({
    request,
    page,
  }: {
    request: any;
    page: Page;
  }) => {
    const token = await authenticate(request, page, uniqueName("gx-"));
    const { seasonName } = await seedSeason(request, token, "GX");

    await page.goto("/");
    await selectSeason(page, seasonName);
    await expect(page.getByText("Seed Opp", { exact: true })).toBeVisible();

    await page
      .locator("main")
      .filter({ hasText: "Seed Opp" })
      .last()
      .getByTitle("Edit game")
      .click();
    const dialog = page.getByRole("dialog");
    await dialog.locator('input[type="text"]').last().fill("Should Not Stick");
    await dialog.getByRole("button", { name: "Cancel" }).click();

    await expect(dialog).toHaveCount(0);
    await expect(page.getByText("Seed Opp", { exact: true })).toBeVisible();
    await expect(page.getByText("Should Not Stick")).toHaveCount(0);
  });
});
