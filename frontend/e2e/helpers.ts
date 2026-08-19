import { type Page, type APIRequestContext } from "@playwright/test";

const API = "/api";

// The dev entrypoint bootstraps this admin account (registration requires
// admin approval, so the e2e suite needs an approver).
const ADMIN = { username: "admin", password: "adminpass123" };

let adminToken: string | null = null;

async function getAdminToken(request: APIRequestContext): Promise<string> {
  if (adminToken) return adminToken;
  const res = await request.post(`${API}/auth/login/`, { data: ADMIN });
  if (res.status() !== 200) {
    throw new Error(`admin login failed: ${res.status()}`);
  }
  adminToken = (await res.json()).token;
  return adminToken;
}

/**
 * Register a fresh user, verify their email, and have the admin approve
 * them (the registration flow requires approval). Then log in and store the
 * real auth token + user in localStorage so the app boots authenticated.
 * Returns the token so API-request seeding can authenticate too.
 */
export async function authenticate(
  request: APIRequestContext,
  page: Page,
  username: string,
): Promise<string> {
  // Random suffix avoids username collisions between parallel workers
  const name = `${username}-${Math.random().toString(36).slice(2, 8)}`;
  const email = `${name}@example.com`;

  const res = await request.post(`${API}/auth/register/`, {
    data: { username: name, password: "testpass123", email },
  });
  if (res.status() !== 201) {
    throw new Error(`register failed: ${res.status()}`);
  }
  const body = await res.json();

  const admin = await getAdminToken(request);

  // Verify the email address (dev mode returns the token in the response)
  const verifyRes = await request.post(`${API}/auth/verify_email_confirm/`, {
    data: { token: body.token },
  });
  if (verifyRes.status() !== 200) {
    throw new Error(`email verification failed: ${verifyRes.status()}`);
  }

  // Find the pending user and approve them
  const pendingRes = await request.get(`${API}/auth/pending_users/`, {
    headers: { Authorization: `Token ${admin}` },
  });
  if (pendingRes.status() !== 200) {
    throw new Error(`pending_users failed: ${pendingRes.status()}`);
  }
  const pending = await pendingRes.json();
  const pendingUser = (Array.isArray(pending) ? pending : []).find(
    (u: { username: string }) => u.username === name,
  );
  if (!pendingUser) {
    throw new Error("registered user not found in pending users");
  }
  const approveRes = await request.post(`${API}/auth/approve_user/`, {
    headers: { Authorization: `Token ${admin}` },
    data: { user_id: pendingUser.id },
  });
  if (approveRes.status() !== 200) {
    throw new Error(`approve failed: ${approveRes.status()}`);
  }

  // Log in as the approved user to obtain a real auth token
  const loginRes = await request.post(`${API}/auth/login/`, {
    data: { username: name, password: "testpass123" },
  });
  if (loginRes.status() !== 200) {
    throw new Error(`login failed: ${loginRes.status()}`);
  }
  const loginBody = await loginRes.json();

  await page.addInitScript(
    ({ token, user }) => {
      localStorage.setItem("auth_token", token);
      localStorage.setItem("auth_user", JSON.stringify(user));
    },
    { token: loginBody.token, user: loginBody.user },
  );
  return loginBody.token;
}
