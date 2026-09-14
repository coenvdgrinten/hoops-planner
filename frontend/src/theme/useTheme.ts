import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "theme";

/**
 * Resolve the theme the app should show right now.
 *
 * Precedence: explicit user choice (localStorage) → OS preference
 * (`prefers-color-scheme`) → light.
 *
 * NOTE: index.html contains an inline script that applies the SAME
 * resolution before first paint (to avoid a flash of the wrong theme).
 * Keep the two in sync.
 */
function resolveInitial(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  if (window.matchMedia("(prefers-color-scheme: dark)").matches) return "dark";
  return "light";
}

/** Apply the theme to <html> so every CSS custom property re-resolves. */
function apply(theme: Theme): void {
  document.documentElement.setAttribute("data-theme", theme);
}

/**
 * Theme state + toggle for the whole app (see theme.css for the palettes).
 *
 * - The active theme lives as a `data-theme` attribute on <html>; all colors
 *   flow through the design tokens, so flipping the attribute re-skins
 *   everything without touching component CSS.
 * - An explicit choice is persisted to localStorage and wins over the OS
 *   setting forever (until changed again).
 * - While no explicit choice is stored, the app follows the OS preference
 *   and reacts to it changing live.
 */
export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(resolveInitial);

  // Keep the attribute in sync with state (also re-applies after the
  // inline boot script, which is idempotent).
  useEffect(() => {
    apply(theme);
  }, [theme]);

  // Follow live OS changes while the user hasn't made an explicit choice.
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e: MediaQueryListEvent) => {
      if (!localStorage.getItem(STORAGE_KEY)) {
        setThemeState(e.matches ? "dark" : "light");
      }
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const setTheme = useCallback((next: Theme) => {
    localStorage.setItem(STORAGE_KEY, next);
    setThemeState(next);
  }, []);

  const toggle = useCallback(() => {
    setTheme(theme === "light" ? "dark" : "light");
  }, [theme, setTheme]);

  return { theme, setTheme, toggle };
}
