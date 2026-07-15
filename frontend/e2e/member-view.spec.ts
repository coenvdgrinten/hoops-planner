import { test, expect, type Page, type APIRequestContext } from "@playwright/test";

const API = "/api";

/**
 * Register a fresh user via the API and store the returned token + user in
 * localStorage so the app boots authenticated (the backend requires auth).
 * Returns the token so API-request seeding can authenticate too.
 */
async function authenticate(
  request: APIRequestContext,
  page: Page,
  username: string,
): Promise<string> {
  const res = await request.post(`${API}/auth/register/`, {
    data: { username, password: "testpass123", email: `${username}@example.com` },
  });
  expect(res.status(), "register should succeed").toBe(201);
  const body = await res.json();

  await page.addInitScript(
    ({ token, user }) => {
      localStorage.setItem("auth_token", token);
      localStorage.setItem("auth_user", JSON.stringify(user));
    },
    { token: body.token, user: body.user },
  );
  return body.token;
}

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
    teamName = `Team ${Date.now()}`;
    const token = await authenticate(request, page, `mv-${Date.now()}`);
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
    await page.getByPlaceholder("Team name (e.g. Vido X14-1)").fill("Vido X99-New");
    // The add-team form is the only visible team-edit-form at this point
    await page.locator("form, div").filter({ has: page.getByPlaceholder("Team name (e.g. Vido X14-1)") }).getByRole("button", { name: "Save" }).click();

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
    await page.getByPlaceholder("Team name (e.g. Vido X14-1)").fill("Doomed Team");
    await page.locator("form, div").filter({ has: page.getByPlaceholder("Team name (e.g. Vido X14-1)") }).getByRole("button", { name: "Save" }).click();
    const teamId = await teamIdFor(page, "Doomed Team");

    const group = page.getByTestId(`team-group-${teamId}`);
    page.once("dialog", (dialog) => dialog.accept());
    await group.getByTestId(`team-delete-${teamId}`).click();

    await expect(page.getByTestId(/^team-header-\d+$/).filter({ hasText: "Doomed Team" })).toHaveCount(0);
  });

  test("adds a player to a team", async ({ page }) => {
    await page.goto("/");
    await openMembers(page);

    const teamId = await teamIdFor(page, teamName);
    const group = page.getByTestId(`team-group-${teamId}`);
    await group.getByTestId(`team-header-${teamId}`).click();
    await group.getByTestId(`add-player-${teamId}`).click();

    const form = group.locator("div").filter({ has: page.getByPlaceholder("First name") }).last();
    await form.getByPlaceholder("First name").fill("Eve");
    await form.getByPlaceholder("Last name").fill("Newbie");
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
    const form = group.filter({ has: page.getByPlaceholder("Last name") }).last();
    await form.getByPlaceholder("Last name").fill("Renamed");
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

    page.once("dialog", (dialog) => dialog.accept());
    await page.getByTestId(`player-delete-${playerId}`).click();

    await expect(page.getByText("Alice NoCert")).toHaveCount(0);
  });
});
