import type { DriveStep } from "driver.js";

/**
 * Data-driven step definitions for the guided tour (issue #8).
 *
 * Every entry is a {target, instruction} pair: a CSS selector pointing at a
 * real element plus the text shown in the popover. Future features extend
 * the tour by adding entries here — no engine changes required.
 */

const SEASON_TOGGLE = '[data-testid="season-dropdown-toggle"]';
const FILL_BAR = '[data-testid="fill-rate-bar"]';
const GAME_CARD = '[data-testid^="game-card"]';
const TASK_CHIP = '[data-testid^="task-chip-"]';
const ASSIGNMENT_PANEL = '[data-testid="assignment-panel"]';
const PANEL_SEARCH = 'input[aria-label="Search member or team"]';
const EXPORT_PDF = '[data-testid="export-pdf-btn"]';

function step(
  element: string,
  title: string,
  description: string,
  extra: Partial<DriveStep> = {},
): DriveStep {
  return { element, popover: { title, description }, ...extra };
}

/**
 * Build the step list for the current situation.
 *
 * - Without a selected season the tour is a single "gate" step pointing at
 *   the season picker. It is deliberately informational: the spotlight
 *   overlay blocks the rest of the app while it is open, so rather than try
 *   to drive the user through the dropdown mid-tour, we point at the control
 *   and tell them to pick a season and then use ? Help for the full walk.
 * - With a season, the full core-planning-loop tour. Steps whose target does
 *   not exist yet (e.g. no game cards for an empty season) wait briefly and
 *   skip themselves; the assignment-panel steps are included only when the
 *   panel is actually open, so the progress counter always matches reality.
 *
 * `panelOpen` is passed in instead of being sniffed from the DOM because the
 * panel is always mounted (kept warm for its query cache) and merely hidden
 * with `display: none` when closed — a presence check cannot tell them apart.
 */
export function buildTourSteps(seasonId: number | null, panelOpen: boolean): DriveStep[] {
  if (!seasonId) {
    return [
      step(
        SEASON_TOGGLE,
        "Pick a season",
        "Everything in the planner belongs to a season. Close this, pick a season from here, then press ? Help in the top bar to walk through the full flow.",
      ),
    ];
  }

  const steps: DriveStep[] = [
    step(
      SEASON_TOGGLE,
      "Pick a season",
      "All schedules belong to a season. Switch seasons from here — the planner, statistics, and exports all follow your choice.",
    ),
    step(
      FILL_BAR,
      "Schedule completeness",
      "This bar shows what share of all task slots is filled. Work towards 100% before you export the schedule.",
      { waitForElement: 3000 },
    ),
    step(
      GAME_CARD,
      "One card per game",
      "Each card is one game: the teams, time, location, and its task chips below. Away games have no tasks and live in the Availability view.",
      { waitForElement: 3000 },
    ),
    step(
      TASK_CHIP,
      "Task slots",
      "Every chip is one job — referee, scorer, timer, or 24-second operator. Red means unfilled, green means filled, and a warning sign marks a conflict. Click a chip to assign someone.",
      { waitForElement: 3000 },
    ),
  ];

  if (panelOpen) {
    steps.push(
      step(
        ASSIGNMENT_PANEL,
        "Who can take this task?",
        "The panel lists everyone eligible for the selected slot. Members who cannot take the task are greyed out with the reason, and the best candidates are ranked for you.",
      ),
      step(
        PANEL_SEARCH,
        "Find people fast",
        "Search by member or team name, or expand a team header to browse its full roster. Click the + next to a member to assign them.",
      ),
    );
  }

  steps.push(
    step(
      EXPORT_PDF,
      "Share the schedule",
      "When planning is done, export the schedule as a PDF or CSV (or a calendar file) and send it to your members.",
    ),
  );

  return steps;
}
