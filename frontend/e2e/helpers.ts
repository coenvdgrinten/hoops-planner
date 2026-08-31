import { type Page, type APIRequestContext } from "@playwright/test";

const API = "/api";

// The dev entrypoint bootstraps this admin account (registration requires
// admin approval, so the e2e suite needs an approver).
const ADMIN = { username: "admin", password: "admin" };

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

/**
 * Generate a unique name for test data (teams, players, seasons, ...).
 *
 * Why this exists: the backend matches teams by name (globally unique) and
 * players by first+last name via get_or_create, so two parallel tests using
 * the same fixed name would share one database row. Every piece of test data
 * that ends up in a globally-keyed column should therefore carry a unique
 * suffix — use this instead of rolling your own `Date.now()` templates.
 *
 * Implementation notes:
 * - timestamp + random tail: parallel workers are separate processes and can
 *   call this within the same millisecond, so the random part rules out
 *   collisions.
 * - the suffix is appended WITHOUT a space: the backend infers age
 *   categories from team names with word-boundary regexes (\bX14\b), and a
 *   spaced token could theoretically form a boundary and misfire.
 */
export function uniqueName(base: string): string {
  const stamp = Date.now().toString(36);
  const rand = Math.random().toString(36).slice(2, 8);
  return `${base}${stamp}${rand}`;
}

/**
 * Fetch ALL items from a paginated list endpoint (page size is fixed at 100
 * server-side). Newly created records land at the END of the list, so reading
 * only page 1 silently misses them once the DB holds more than 100 rows.
 */
export async function fetchAllPages<T>(
  request: APIRequestContext,
  path: string,
  token: string,
): Promise<T[]> {
  const items: T[] = [];
  for (let p = 1; p <= 50; p++) {
    const res = await request.get(`${path}?page=${p}`, {
      headers: { Authorization: `Token ${token}` },
    });
    if (res.status() !== 200) {
      throw new Error(`GET ${path}?page=${p} failed: ${res.status()}`);
    }
    const body = (await res.json()) as
      | T[]
      | { results?: T[]; count?: number };
    const pageItems = Array.isArray(body) ? body : (body.results ?? []);
    items.push(...pageItems);
    // Stop when we've seen everything or hit an empty page.
    const count = !Array.isArray(body) ? body.count : undefined;
    if (count !== undefined ? items.length >= count : pageItems.length === 0) {
      break;
    }
  }
  return items;
}
