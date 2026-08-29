import { test, expect, type Page } from "@playwright/test";
import { authenticate } from "./helpers";

const API = "/api";

/** Register + verify + approve a user via the API (no UI). */
async function seedApprovedUser(
  request: Parameters<typeof authenticate>[0],
  username: string,
): Promise<void> {
  const res = await request.post(`${API}/auth/register/`, {
    data: { username, password: "testpass123", email: `${username}@example.com` },
  });
  expect(res.status(), "register should succeed").toBe(201);
  const body = await res.json();

  const adminRes = await request.post(`${API}/auth/login/`, {
    data: { username: "admin", password: "admin" },
  });
  expect(adminRes.status(), "admin login should succeed").toBe(200);
  const adminToken = (await adminRes.json()).token;

  const verifyRes = await request.post(`${API}/auth/verify_email_confirm/`, {
    data: { token: body.token },
  });
  expect(verifyRes.status(), "email verification should succeed").toBe(200);

  const pendingRes = await request.get(`${API}/auth/pending_users/`, {
    headers: { Authorization: `Token ${adminToken}` },
  });
  const pending = await pendingRes.json();
  const pendingUser = (Array.isArray(pending) ? pending : []).find(
    (u: { username: string }) => u.username === username,
  );
  expect(pendingUser, "user should be pending").toBeTruthy();

  const approveRes = await request.post(`${API}/auth/approve_user/`, {
    headers: { Authorization: `Token ${adminToken}` },
    data: { user_id: pendingUser.id },
  });
  expect(approveRes.status(), "approve should succeed").toBe(200);
}

test.describe("Auth", () => {
  test("logs in with valid credentials", async ({ request, page }: { request: any; page: Page }) => {
    const username = `au-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    await seedApprovedUser(request, username);

    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Sign In" })).toBeVisible();
    await page.getByLabel("Username or Email").fill(username);
    await page.getByLabel("Password").fill("testpass123");
    await page.getByRole("button", { name: "Sign In", exact: true }).click();

    // Logged in — the app shell replaces the login form
    await expect(page.getByRole("heading", { name: "Sign In" })).toHaveCount(0);
    await expect(page.getByAltText("Logo")).toBeVisible();
    await expect(page.getByRole("button", { name: "Schedule Planner" })).toBeVisible();
  });

  test("shows an error for a wrong password", async ({ page }: { page: Page }) => {
    await page.goto("/");
    await page.getByLabel("Username or Email").fill("nobody-here");
    await page.getByLabel("Password").fill("wrongpass");
    await page.getByRole("button", { name: "Sign In", exact: true }).click();

    await expect(page.getByText("Invalid credentials.")).toBeVisible();
    // Still on the login form
    await expect(page.getByRole("heading", { name: "Sign In" })).toBeVisible();
  });

  test("registers a new account via the form", async ({ page }: { page: Page }) => {
    const username = `reg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    await page.goto("/");
    await page.getByRole("button", { name: "Register" }).click();
    await expect(page.getByRole("heading", { name: "Create Account" })).toBeVisible();

    await page.getByLabel("Username").fill(username);
    await page.getByLabel("Email").fill(`${username}@example.com`);
    await page.getByLabel("Password").fill("testpass123");
    await page.getByRole("button", { name: "Create Account" }).click();

    await expect(page.getByText(/Account created/)).toBeVisible();
    // Form switches back to sign-in mode
    await expect(page.getByRole("heading", { name: "Sign In" })).toBeVisible();
  });

  test("blocks login until an admin approves the account", async ({ request, page }: { request: any; page: Page }) => {
    const username = `pend-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    // Register + verify, but do NOT approve
    const res = await request.post(`${API}/auth/register/`, {
      data: { username, password: "testpass123", email: `${username}@example.com` },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    const verifyRes = await request.post(`${API}/auth/verify_email_confirm/`, {
      data: { token: body.token },
    });
    expect(verifyRes.status()).toBe(200);

    await page.goto("/");
    await page.getByLabel("Username or Email").fill(username);
    await page.getByLabel("Password").fill("testpass123");
    await page.getByRole("button", { name: "Sign In", exact: true }).click();

    await expect(page.getByText(/pending approval/i)).toBeVisible();
    await expect(page.getByRole("heading", { name: "Sign In" })).toBeVisible();
  });

  test("logs out and returns to the login screen", async ({ request, page }: { request: any; page: Page }) => {
    await authenticate(request, page, `lo-${Date.now()}`);
    await page.goto("/");
    await expect(page.getByAltText("Logo")).toBeVisible();

    await page.getByRole("button", { name: "Logout" }).click();
    await expect(page.getByRole("heading", { name: "Sign In" })).toBeVisible();
  });

  test("stays logged in across a page reload", async ({ request, page }: { request: any; page: Page }) => {
    await authenticate(request, page, `pr-${Date.now()}`);
    await page.goto("/");
    await expect(page.getByAltText("Logo")).toBeVisible();

    await page.reload();
    await expect(page.getByAltText("Logo")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Sign In" })).toHaveCount(0);
  });
});
