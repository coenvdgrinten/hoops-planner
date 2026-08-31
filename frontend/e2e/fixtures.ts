import { test as base } from "@playwright/test";

/**
 * Shared e2e test object.
 *
 * All specs import `test` from here (instead of directly from
 * "@playwright/test") so future isolation guarantees (worker-scoped data,
 * cleanup fixtures, ...) can be added in ONE place instead of in every spec.
 *
 * Note on global state: the backend keeps a single SiteConfig row (club name
 * shown in the header). Resetting it via an auto-fixture after EVERY test
 * races with the settings tests that intentionally change it mid-test, so the
 * rule is instead:
 *   - tests that mutate global state restore it themselves (see the brand
 *     tests in settings.spec.ts, which run serially), and
 *   - global-setup.ts wipes the club name once before the suite starts, so a
 *     crashed previous run can't poison this one.
 */
export const test = base;

export { expect } from "@playwright/test";
