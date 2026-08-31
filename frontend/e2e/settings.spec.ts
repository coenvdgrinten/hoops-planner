import { test, expect, type Page } from "./fixtures";
import { authenticate, uniqueName } from "./helpers";

const API = "/api";

async function loginAdmin(page: Page): Promise<void> {
  await page.goto("/");
  await page.getByLabel("Username or Email").fill("admin");
  await page.getByLabel("Password").fill("admin");
  await page.getByRole("button", { name: "Sign In", exact: true }).click();
  await expect(page.getByAltText("Logo")).toBeVisible();
}

/** The app has no URL routing — views are switched via the sidebar. */
async function openSettings(page: Page): Promise<void> {
  await page.goto("/");
  await page.getByRole("button", { name: "Settings" }).click();
  await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
}

test.describe("Settings", () => {
  // The brand-name tests mutate a SINGLE global SiteConfig row, so they must
  // not run concurrently with each other (or with anything asserting the
  // header text). Each test restores the brand itself (see below), which also
  // keeps them safe against the rest of the suite.
  test.describe.configure({ mode: "serial" });

  /** Clear the global brand again — used as cleanup for the brand tests. */
  async function clearBrand(page: Page): Promise<void> {
    await page.goto("/");
    await openSettings(page);
    const input = page.locator("#brand-input");
    await input.fill("");
    await input.press("Enter");
  }

  test("saves a new brand name to the top bar", async ({ request, page }: { request: any; page: Page }) => {
    const brand = uniqueName("Brand ");
    await authenticate(request, page, uniqueName("st-"));
    await openSettings(page);

    try {
      const input = page.locator("#brand-input");
      await input.fill(brand);
      await input.press("Enter");

      // Top bar now shows the brand next to "Hoops Planner" (unique timestamp suffix)
      await expect(page.getByText(brand)).toBeVisible();

      // Persists across navigation
      await page.getByRole("button", { name: "Schedule Planner" }).click();
      await expect(page.getByText(brand)).toBeVisible();
    } finally {
      // Brand is global state — restore it so we don't leak into other tests.
      // Best-effort: never mask the real failure.
      try {
        await clearBrand(page);
      } catch {
        // global-setup resets the brand for the next run anyway
      }
    }
  });

  test("clearing the brand restores the default title", async ({ request, page }: { request: any; page: Page }) => {
    const brand = uniqueName("Temp ");
    await authenticate(request, page, uniqueName("sc-"));
    await openSettings(page);

    try {
      const input = page.locator("#brand-input");
      await input.fill(brand);
      await input.press("Enter");
      await expect(page.getByText(brand)).toBeVisible();

      await input.fill("");
      await input.press("Enter");
      await expect(page.getByText(brand)).toHaveCount(0);
    } finally {
      // Same global-state hygiene as above (usually a no-op here, since the
      // test already cleared the brand).
      try {
        await clearBrand(page);
      } catch {
        // ignore
      }
    }
  });

  test("updates team task requirements and persists them", async ({ request, page }: { request: any; page: Page }) => {
    const token = await authenticate(request, page, uniqueName("ts-"));
    const teamName = uniqueName("T");
    const res = await request.post(`${API}/players/import_members/`, {
      headers: { Authorization: `Token ${token}` },
      data: {
        csv_text: `first_name,last_name,team,is_coach,referee_certification\nBob,Brown,${teamName},False,F`,
        upsert: true,
      },
    });
    expect(res.status()).toBe(201);

    await openSettings(page);

    const row = page.locator("table tr").filter({ hasText: teamName });
    await expect(row).toBeVisible();

    // Change the required-referees count for this team
    const refereeInput = row.locator('input[type="number"]').first();
    await refereeInput.fill("2");
    await refereeInput.blur();

    // Reload and verify the value persisted (reload resets the app to the
    // planner view, so navigate back to Settings)
    await page.reload();
    await openSettings(page);
    const reloadedRow = page.locator("table tr").filter({ hasText: teamName });
    await expect(reloadedRow.locator('input[type="number"]').first()).toHaveValue("2");
  });

  test("approves a pending user from the pending users panel", async ({ request, page }: { request: any; page: Page }) => {
    const username = uniqueName("pu-");
    // Register + verify via API, leave unapproved
    const res = await request.post(`${API}/auth/register/`, {
      data: { username, password: "testpass123", email: `${username}@example.com` },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    const verifyRes = await request.post(`${API}/auth/verify_email_confirm/`, {
      data: { token: body.token },
    });
    expect(verifyRes.status()).toBe(200);

    await loginAdmin(page);
    await openSettings(page);
    await expect(page.getByRole("heading", { name: "Pending Users" })).toBeVisible();

    const row = page.locator("table tr").filter({ hasText: username });
    await expect(row).toBeVisible();

    await row.getByRole("button", { name: "Approve" }).click();
    await expect(row).toHaveCount(0);

    // The approved user can now log in
    const loginRes = await request.post(`${API}/auth/login/`, {
      data: { username, password: "testpass123" },
    });
    expect(loginRes.status()).toBe(200);
  });

  test("rejects a pending user from the pending users panel", async ({ request, page }: { request: any; page: Page }) => {
    const username = uniqueName("rj-");
    const res = await request.post(`${API}/auth/register/`, {
      data: { username, password: "testpass123", email: `${username}@example.com` },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    const verifyRes = await request.post(`${API}/auth/verify_email_confirm/`, {
      data: { token: body.token },
    });
    expect(verifyRes.status()).toBe(200);

    await loginAdmin(page);
    // The Reject button asks via a native confirm() dialog
    page.on("dialog", (d) => d.accept());
    await openSettings(page);
    await expect(page.getByRole("heading", { name: "Pending Users" })).toBeVisible();

    const row = page.locator("table tr").filter({ hasText: username });
    await expect(row).toBeVisible();

    await row.getByRole("button", { name: "Reject" }).click();
    await expect(row).toHaveCount(0);

    // The rejected user can no longer log in
    const loginRes = await request.post(`${API}/auth/login/`, {
      data: { username, password: "testpass123" },
    });
    expect(loginRes.status()).not.toBe(200);
  });

  test("hides the pending users panel from non-staff users", async ({ request, page }: { request: any; page: Page }) => {
    await authenticate(request, page, uniqueName("ns-"));
    await openSettings(page);
    await expect(page.getByRole("heading", { name: "Pending Users" })).toHaveCount(0);
  });
});
