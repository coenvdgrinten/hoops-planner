import { type Page, type APIRequestContext } from "@playwright/test";

const API = "/api";

/**
 * Register a fresh user via the API and store the returned token + user in
 * localStorage so the app boots authenticated (the backend requires auth).
 * Returns the token so API-request seeding can authenticate too.
 */
export async function authenticate(
  request: APIRequestContext,
  page: Page,
  username: string,
): Promise<string> {
  const res = await request.post(`${API}/auth/register/`, {
    data: { username, password: "testpass123", email: `${username}@example.com` },
  });
  if (res.status() !== 201) {
    throw new Error(`register failed: ${res.status()}`);
  }
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
