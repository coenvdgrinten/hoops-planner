import { request, type FullConfig } from "@playwright/test";

const API = "/api";

// Dev bootstrap account created by the backend entrypoint (DEBUG mode).
const ADMIN = { username: "admin", password: "admin" };

/**
 * Global setup: seed the database with demo data before the suite runs.
 *
 * This lets you log in and click around / debug without importing CSVs by
 * hand. It calls the admin-only `/api/seed/` endpoint (enabled in DEBUG),
 * which is idempotent — safe to run on every test invocation.
 *
 * Seeding is best-effort: if the backend isn't reachable or the admin
 * account doesn't exist yet, we warn and continue instead of failing the
 * whole suite. To seed manually (e.g. local SQLite without the entrypoint):
 *
 *     uv run manage.py seed_demo
 */
export default async function globalSetup(fullConfig: FullConfig) {
  const baseURL = fullConfig.projects[0]?.use?.baseURL ?? "http://localhost:5173";

  // Generous timeout: wiping a bloated DB and seeding can take a while.
  const context = await request.newContext({ baseURL, timeout: 120_000 });
  const auth = { headers: {} as Record<string, string> };

  try {
    // Obtain an admin token.
    const loginRes = await context.post(`${API}/auth/login/`, { data: ADMIN });
    if (loginRes.status() !== 200) {
      console.warn(
        `\n[e2e seed] Could not log in as admin (${loginRes.status()}).\n` +
          "[e2e seed] Skipping auto-seed. Start the app (./run) or seed manually:\n" +
          "           uv run manage.py seed_demo\n",
      );
      return;
    }
    const { token } = (await loginRes.json()) as { token: string };
    auth.headers.Authorization = `Token ${token}`;

    // Wipe test leftovers from previous runs. Tests create seasons/teams
    // freely and never clean up, so without this the DB grows unbounded and
    // every list endpoint (and the seed below) gets slower over time.
    // Deleting a season cascades to its games/tasks/assignments; deleting a
    // team cascades to its players. Re-delete page 1 until it's empty
    // (deleting shifts the pagination window).
    for (const kind of ["seasons", "teams"] as const) {
      let guard = 0;
      while (guard++ < 500) {
        const res = await context.get(`${API}/${kind}/?page=1`, {
          headers: auth.headers,
        });
        if (res.status() !== 200) break;
        const body = (await res.json()) as
          | { id: number }[]
          | { results?: { id: number }[] };
        const items = Array.isArray(body) ? body : (body.results ?? []);
        if (items.length === 0) break;
        for (const item of items) {
          await context.delete(`${API}/${kind}/${item.id}/`, {
            headers: auth.headers,
          });
        }
      }
    }

    // Reset the global club name: a crashed previous run may have left a test
    // brand behind, which breaks exact-match assertions on the header text.
    // Done here (not in an auto-fixture) because resetting per-test would race
    // with the settings tests that intentionally change the brand mid-test.
    await context.put(`${API}/site-config/`, {
      headers: auth.headers,
      data: { club_name: "" },
    });

    // Seed demo data (idempotent).
    const seedRes = await context.post(`${API}/seed/`, {
      headers: auth.headers,
    });
    if (seedRes.status() !== 201) {
      const body = await seedRes.text().catch(() => "");
      console.warn(
        `\n[e2e seed] Seeding failed (${seedRes.status()}): ${body}\n` +
          "[e2e seed] Continuing without demo data.\n",
      );
      return;
    }

    const summary = (await seedRes.json()) as {
      teams?: number;
      players?: number;
      games?: number;
      credentials?: { username: string; password: string }[];
    };
    console.log(
      `\n[e2e seed] Demo data ready — ${summary.teams} teams, ` +
        `${summary.players} players, ${summary.games} games.\n` +
        "[e2e seed] Log in with any of:\n" +
        (summary.credentials ?? [])
          .map((c) => `           ${c.username} / ${c.password}`)
          .join("\n") +
        "\n",
    );
  } finally {
    await context.dispose();
  }
}
