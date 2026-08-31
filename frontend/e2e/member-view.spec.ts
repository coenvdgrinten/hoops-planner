import { test, expect, type Page } from "./fixtures";
import type { APIRequestContext } from "@playwright/test";
import { authenticate, uniqueName } from "./helpers";

const API = "/api";


async function seedMembers(
  request: APIRequestContext,
  token: string,
  teamName: string,
) {
  const membersCsv =
    `first_name,last_name,team,is_coach,referee_certification\n` +
    `Alice,NoCert,${teamName},False,NONE\n` +
    `Bob,FDiploma,${teamName},False,F\n` +
    `Charlie,Senior,${teamName},False,SENIOR\n` +
    `Diana,Coach,${teamName},True,F`;
  const res = await request.post(`${API}/players/import_members/`, {
    headers: { Authorization: `Token ${token}` },
    data: { csv_text: membersCsv, upsert: true },
  });
  expect(res.status(), "import_members should succeed").toBe(201);
}

async function openMembers(page: Page) {
  const membersBtn = page
    .getByRole("navigation")
    .getByRole("button", { name: "Member Roster" });
  await membersBtn.click();
  await expect(membersBtn).toHaveClass(/active/);
}

/** Resolve the numeric id of the team whose header shows `name`. */
async function teamIdFor(page: Page, name: string): Promise<string> {
  const header = page.getByTestId(/^team-header-\d+$/).filter({ hasText: name }).first();
  const id = (await header.getAttribute("data-testid"))!.replace("team-header-", "");
  return id;
}

test.describe("Member View", () => {
  // The backend is a single shared SQLite DB; run sequentially to avoid
  // concurrent-write races and shared-seed mutation between tests.
  test.describe.configure({ mode: "serial" });

  let teamName: string;

  test.beforeEach(async ({ request, page }) => {
    teamName = uniqueName("Team ");
    const token = await authenticate(request, page, uniqueName("mv-"));
    await seedMembers(request, token, teamName);
  });

  test("shows member roster view", async ({ page }) => {
    await page.goto("/");
    await openMembers(page);
    await expect(page.getByRole("heading", { name: "Member Roster" })).toBeVisible();
  });

  test("displays imported members", async ({ page }) => {
    await page.goto("/");
    await openMembers(page);

    const teamId = await teamIdFor(page, teamName);
    await page.getByTestId(`team-header-${teamId}`).click();

    await expect(page.getByText("Alice NoCert")).toBeVisible();
    await expect(page.getByText("Bob FDiploma")).toBeVisible();
  });

  test("shows cert class for NONE certification", async ({ page }) => {
    await page.goto("/");
    await openMembers(page);

    const teamId = await teamIdFor(page, teamName);
    await page.getByTestId(`team-header-${teamId}`).click();

    const aliceRow = page.getByText("Alice NoCert").first();
    await expect(aliceRow).toBeVisible();
    const certSelect = aliceRow.locator("..").locator("..").getByTestId(/^cert-select-\d+$/);
    await expect(certSelect).toHaveClass(/cert-none/);
  });

  test("shows cert class for F certification", async ({ page }) => {
    await page.goto("/");
    await openMembers(page);

    const teamId = await teamIdFor(page, teamName);
    await page.getByTestId(`team-header-${teamId}`).click();

    const bobRow = page.getByText("Bob FDiploma").first();
    await expect(bobRow).toBeVisible();
    const certSelect = bobRow.locator("..").locator("..").getByTestId(/^cert-select-\d+$/);
    await expect(certSelect).toHaveClass(/cert-low/);
  });

  test("shows cert class for SENIOR certification", async ({ page }) => {
    await page.goto("/");
    await openMembers(page);

    const teamId = await teamIdFor(page, teamName);
    await page.getByTestId(`team-header-${teamId}`).click();

    const charlieRow = page.getByText("Charlie Senior").first();
    await expect(charlieRow).toBeVisible();
    const certSelect = charlieRow.locator("..").locator("..").getByTestId(/^cert-select-\d+$/);
    await expect(certSelect).toHaveClass(/cert-high/);
  });

  test("creates a new team", async ({ page }) => {
    await page.goto("/");
    await openMembers(page);

    await page.getByRole("button", { name: "+ Add Team" }).click();
    await page.getByLabel("Team name").fill("Vido X99-New");
    // The add-team form is the only visible team-edit-form at this point
    await page.locator("form, div").filter({ has: page.getByLabel("Team name") }).getByRole("button", { name: "Save" }).click();

    await expect(page.getByTestId(/^team-header-\d+$/).filter({ hasText: "Vido X99-New" })).toBeVisible();
  });

  test("edits a team name", async ({ page }) => {
    await page.goto("/");
    await openMembers(page);

    const teamId = await teamIdFor(page, teamName);
    const group = page.getByTestId(`team-group-${teamId}`);
    await group.getByTestId(`team-edit-${teamId}`).click();

    const nameInput = group.locator("input").first();
    await nameInput.fill(`${teamName} Renamed`);
    await group.getByRole("button", { name: "Save" }).click();

    await expect(page.getByTestId(/^team-header-\d+$/).filter({ hasText: `${teamName} Renamed` })).toBeVisible();
  });

  test("deletes a team", async ({ page }) => {
    await page.goto("/");
    await openMembers(page);

    // Create a throwaway team, then delete it (don't touch the shared seed).
    await page.getByRole("button", { name: "+ Add Team" }).click();
    await page.getByLabel("Team name").fill("Doomed Team");
    await page.locator("form, div").filter({ has: page.getByLabel("Team name") }).getByRole("button", { name: "Save" }).click();
    const teamId = await teamIdFor(page, "Doomed Team");

    const group = page.getByTestId(`team-group-${teamId}`);
    await group.getByTestId(`team-delete-${teamId}`).click();
    // Confirm via the app's delete modal
    await page.getByRole("button", { name: "Delete", exact: true }).click();

    await expect(page.getByTestId(/^team-header-\d+$/).filter({ hasText: "Doomed Team" })).toHaveCount(0);
  });

  test("adds a player to a team", async ({ page }) => {
    await page.goto("/");
    await openMembers(page);

    const teamId = await teamIdFor(page, teamName);
    const group = page.getByTestId(`team-group-${teamId}`);
    await group.getByTestId(`team-header-${teamId}`).click();
    await group.getByTestId(`add-player-${teamId}`).click();

    const form = group.locator("div").filter({ has: page.getByLabel("First name") }).last();
    await form.getByLabel("First name").fill("Eve");
    await form.getByLabel("Last name").fill("Newbie");
    await form.getByRole("button", { name: "Save" }).click();

    await expect(page.getByText("Eve Newbie")).toBeVisible();
  });

  test("edits a player", async ({ page }) => {
    await page.goto("/");
    await openMembers(page);

    const teamId = await teamIdFor(page, teamName);
    const group = page.getByTestId(`team-group-${teamId}`);
    await group.getByTestId(`team-header-${teamId}`).click();

    const aliceRow = page.getByText("Alice NoCert").first();
    const playerId = (await aliceRow
      .locator("..")
      .locator("..")
      .getByTestId(/^player-edit-\d+$/)
      .getAttribute("data-testid"))!.replace("player-edit-", "");

    await page.getByTestId(`player-edit-${playerId}`).click();
    const form = group.filter({ has: page.getByLabel("Last name") }).last();
    await form.getByLabel("Last name").fill("Renamed");
    await form.getByRole("button", { name: "Save" }).click();

    await expect(page.getByText("Alice Renamed")).toBeVisible();
  });

  test("deletes a player", async ({ page }) => {
    await page.goto("/");
    await openMembers(page);

    const teamId = await teamIdFor(page, teamName);
    const group = page.getByTestId(`team-group-${teamId}`);
    await group.getByTestId(`team-header-${teamId}`).click();

    const aliceRow = page.getByText("Alice NoCert").first();
    const playerId = (await aliceRow
      .locator("..")
      .locator("..")
      .getByTestId(/^player-delete-\d+$/)
      .getAttribute("data-testid"))!.replace("player-delete-", "");

    await page.getByTestId(`player-delete-${playerId}`).click();
    // Confirm via the app's delete modal
    await page.getByRole("button", { name: "Delete", exact: true }).click();

    await expect(page.getByText("Alice NoCert")).toHaveCount(0);
  });

  test("moves a player to another team", async ({ page }) => {
    await page.goto("/");
    await openMembers(page);

    // Create a second team to move into
    const destTeam = uniqueName("Dest ");
    await page.getByRole("button", { name: "+ Add Team" }).click();
    await page.getByLabel("Team name").fill(destTeam);
    await page
      .locator("form, div")
      .filter({ has: page.getByLabel("Team name") })
      .getByRole("button", { name: "Save" })
      .click();
    const destId = await teamIdFor(page, destTeam);

    // Open Alice's edit form in her current team
    const teamId = await teamIdFor(page, teamName);
    const group = page.getByTestId(`team-group-${teamId}`);
    await group.getByTestId(`team-header-${teamId}`).click();

    const aliceRow = page.getByText("Alice NoCert").first();
    const playerId = (await aliceRow
      .locator("..")
      .locator("..")
      .getByTestId(/^player-edit-\d+$/)
      .getAttribute("data-testid"))!.replace("player-edit-", "");

    await page.getByTestId(`player-edit-${playerId}`).click();
    await page.getByTestId(`player-team-${playerId}`).selectOption({ label: destTeam });
    await page
      .locator("div")
      .filter({ has: page.getByLabel("Last name") })
      .last()
      .getByRole("button", { name: "Save" })
      .click();

    // Reload to drop any stale client-side expansion state, then verify
    await page.reload();
    await openMembers(page);

    const destGroup = page.getByTestId(`team-group-${destId}`);
    await destGroup.getByTestId(`team-header-${destId}`).click();
    await expect(destGroup.getByText("Alice NoCert")).toBeVisible();

    const srcGroup = page.getByTestId(`team-group-${teamId}`);
    await srcGroup.getByTestId(`team-header-${teamId}`).click();
    await expect(srcGroup.getByText("Alice NoCert")).toHaveCount(0);
  });
});
