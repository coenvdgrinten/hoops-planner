import { chromium } from "playwright-core";

const BASE = "http://localhost:5173";
const API = `${BASE}/api`;
const OUT = "../docs/screenshots";

// Log in as the dev bootstrap admin and return { token, user }.
async function login() {
  const res = await fetch(`${API}/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "admin", password: "admin" }),
  });
  if (res.status !== 200) throw new Error(`login failed: ${res.status}`);
  return res.json();
}

async function main() {
  const { token, user } = await login();
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();

  // Pre-seed auth so the app loads straight into the authenticated shell.
  await page.addInitScript(
    ({ t, u }) => {
      localStorage.setItem("auth_token", t);
      localStorage.setItem("auth_user", JSON.stringify(u));
    },
    { t: token, u: user },
  );

  await page.goto(BASE, { waitUntil: "networkidle" });

  // Select the first available season.
  await page.getByRole("button", { name: /Select season/i }).click();
  const seasonBtn = page
    .getByRole("button")
    .filter({ hasText: /^\d{4}-\d{4}$/ })
    .first();
  await seasonBtn.click();

  // Wait for task cards to finish loading on the planner.
  await page.waitForTimeout(2500);

  // Open the first task's assignment panel so the suggested-candidates
  // sidebar is visible in the screenshot.
  const firstChip = page.locator('[data-testid^="task-chip-"]').first();
  if (await firstChip.count()) {
    await firstChip.click();
    await page.waitForSelector('[data-testid="assignment-panel"]', { timeout: 5000 });
    // Let the candidate suggestions query resolve.
    await page.waitForTimeout(1500);
  }

  // 1) Schedule Planner
  await page.screenshot({ path: `${OUT}/planner.png` });
  console.log("captured planner.png");

  // 2) Member Roster
  await page.getByRole("button", { name: /Member Roster/i }).click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/members.png` });
  console.log("captured members.png");

  // 3) Statistics
  await page.getByRole("button", { name: /Statistics/i }).click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/statistics.png` });
  console.log("captured statistics.png");

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
