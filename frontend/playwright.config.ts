import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  // Seed demo data (users, teams, schedules) before the suite so you can log
  // in and click around / debug without importing CSVs by hand. Best-effort:
  // it warns and continues if the backend isn't reachable.
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  // CI (ubuntu-latest = 2 vCPUs) runs 2 workers; locally we default to ~half
  // the core count. Validated stable at 12 workers via scripts/e2e-soak.sh.
  workers: process.env.CI ? 2 : undefined,
  reporter: "list",
  // Generous timeouts: the suite drives a real backend (PDF generation,
  // multi-page list fetches) across many parallel workers, so under CPU
  // contention a single action can exceed Playwright's tight 5s/30s defaults
  // and flake. These give every test headroom to let the UI catch up. CI runs
  // fewer workers than a local stress run, so it has even more margin.
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: "http://localhost:5173",
    actionTimeout: 15_000,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  // No webServer config — assumes app is already running (Docker or manual)
});
