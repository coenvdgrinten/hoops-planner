import { test, expect } from "./fixtures";
import { authenticate } from "./helpers";

/**
 * Dark mode (top-bar toggle, persistence, OS-preference fallback).
 *
 * Theme resolution order under test: stored choice (localStorage "theme")
 * → OS preference (prefers-color-scheme) → light. The inline boot script in
 * index.html applies the theme before first paint; useTheme.ts keeps state
 * in sync afterwards. We assert on the `data-theme` attribute on <html> and
 * on the resolved body background (the --color-bg token) as a visual proxy.
 */

const LIGHT_BG = "rgb(248, 249, 252)"; // --color-bg in :root
const DARK_BG = "rgb(20, 22, 28)"; // --color-bg in [data-theme="dark"]

async function currentTheme(page: import("@playwright/test").Page): Promise<string> {
  return page.evaluate(() => document.documentElement.getAttribute("data-theme"));
}

async function bodyBg(page: import("@playwright/test").Page): Promise<string> {
  return page.evaluate(() => getComputedStyle(document.body).backgroundColor);
}

test.describe("Dark mode", () => {
  test("defaults to light, toggles to dark, and back", async ({ request, page }) => {
    await authenticate(request, page, "th-");
    await page.goto("/");
    await expect(page.getByAltText("Logo")).toBeVisible();

    // Fresh context, no stored choice, Playwright's default color scheme is
    // light → the app boots light.
    await expect.poll(() => currentTheme(page)).toBe("light");
    await expect(await bodyBg(page)).toBe(LIGHT_BG);

    const toggle = page.getByTestId("theme-toggle");
    await expect(toggle).toHaveAccessibleName("Switch to dark mode");
    await toggle.click();

    await expect.poll(() => currentTheme(page)).toBe("dark");
    await expect(await bodyBg(page)).toBe(DARK_BG);
    await expect(toggle).toHaveAccessibleName("Switch to light mode");

    // Toggle back.
    await toggle.click();
    await expect.poll(() => currentTheme(page)).toBe("light");
    await expect(await bodyBg(page)).toBe(LIGHT_BG);
  });

  test("choice persists across a reload and beats the OS setting", async ({
    request,
    page,
  }) => {
    await authenticate(request, page, "th-");
    await page.goto("/");
    await expect(page.getByAltText("Logo")).toBeVisible();

    await page.getByTestId("theme-toggle").click();
    await expect.poll(() => currentTheme(page)).toBe("dark");
    await expect(await page.evaluate(() => localStorage.getItem("theme"))).toBe("dark");

    // Reload: the inline boot script must restore dark before React mounts.
    await page.reload();
    await expect(page.getByAltText("Logo")).toBeVisible();
    await expect.poll(() => currentTheme(page)).toBe("dark");
    await expect(await bodyBg(page)).toBe(DARK_BG);

    // A stored choice wins over the OS preference.
    await page.emulateMedia({ colorScheme: "light" });
    await expect(await currentTheme(page)).toBe("dark");
  });

  test("follows the OS preference when no choice is stored", async ({
    request,
    page,
  }) => {
    // Emulate before navigation so the boot script sees it.
    await page.emulateMedia({ colorScheme: "dark" });
    await authenticate(request, page, "th-");
    await page.goto("/");
    await expect(page.getByAltText("Logo")).toBeVisible();

    await expect.poll(() => currentTheme(page)).toBe("dark");
    await expect(await bodyBg(page)).toBe(DARK_BG);
    // Following the OS does NOT store an explicit choice.
    await expect(await page.evaluate(() => localStorage.getItem("theme"))).toBeNull();
  });

  test("reacts live to OS changes while no choice is stored", async ({
    request,
    page,
  }) => {
    await authenticate(request, page, "th-");
    await page.goto("/");
    await expect(page.getByAltText("Logo")).toBeVisible();
    await expect.poll(() => currentTheme(page)).toBe("light");

    // Flip the emulated OS scheme; the hook should follow without a click.
    await page.emulateMedia({ colorScheme: "dark" });
    await expect.poll(() => currentTheme(page)).toBe("dark");
    await expect(await bodyBg(page)).toBe(DARK_BG);

    await page.emulateMedia({ colorScheme: "light" });
    await expect.poll(() => currentTheme(page)).toBe("light");
  });

  test("stored light choice beats a dark OS preference", async ({
    request,
    page,
  }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.addInitScript(() => localStorage.setItem("theme", "light"));
    await authenticate(request, page, "th-");
    await page.goto("/");
    await expect(page.getByAltText("Logo")).toBeVisible();

    await expect.poll(() => currentTheme(page)).toBe("light");
    await expect(await bodyBg(page)).toBe(LIGHT_BG);
  });
});
