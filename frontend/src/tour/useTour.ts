import { useCallback, useEffect, useRef } from "react";
import { driver } from "driver.js";
import "driver.js/dist/driver.css";
import type { Driver } from "driver.js";
import { buildTourSteps } from "./steps";

const COMPLETED_KEY = "tour-completed";

/**
 * Interactive guided tour (issue #8).
 *
 * One module owns the whole tour lifecycle:
 *  - auto-starts on first login (remembered per browser),
 *  - can be replayed anytime via the Help entry,
 *  - when no season is selected it runs a short "gate" variant pointing at
 *    the season picker; once a season is loaded, Help walks the full tour
 *    (the overlay intentionally blocks the app while the tour is open, so
 *    the tour never fights the user for input),
 *  - cleans up completely on unmount so no overlay state survives.
 */
export function useTour(seasonId: number | null, active: boolean, panelOpen: boolean) {
  const driverRef = useRef<Driver | null>(null);

  const stop = useCallback(() => {
    driverRef.current?.destroy();
    driverRef.current = null;
  }, []);

  const start = useCallback(
    (id: number | null, open: boolean) => {
      stop();
      const d = driver({
        steps: buildTourSteps(id, open),
        overlayColor: "rgba(15, 23, 42, 0.6)",
        overlayOpacity: 0.7,
        smoothScroll: true,
        showProgress: true,
        progressText: "{{current}} / {{total}}",
        nextBtnText: "Next",
        prevBtnText: "Back",
        doneBtnText: "Done",
        // Fires synchronously when the user clicks "Done" on the last step.
        // NOTE: providing this hook REPLACES driver.js' built-in advance
        // behaviour for the next/done button, so we must call moveNext()
        // ourselves or the popover stays open.
        onDoneClick: () => {
          localStorage.setItem(COMPLETED_KEY, "1");
          driverRef.current?.moveNext();
        },
      });
      driverRef.current = d;
      d.drive();
    },
    [stop],
  );

  const replay = useCallback(() => {
    localStorage.removeItem(COMPLETED_KEY);
    start(seasonId, panelOpen);
  }, [seasonId, panelOpen, start]);

  const hasCompleted = useCallback(
    () => localStorage.getItem(COMPLETED_KEY) === "1",
    [],
  );

  // Auto-start exactly once per browser, on first login. The hook is called
  // unconditionally (hooks can't be conditional), so it must stay inert while
  // `active` is false — i.e. on the login screen, where a tour overlay would
  // block every click.
  useEffect(() => {
    if (active && !hasCompleted()) {
      start(seasonId, panelOpen);
    }
    return stop;
  }, [active]); // eslint-disable-line react-hooks/exhaustive-deps

  return { start, stop, replay, hasCompleted };
}
