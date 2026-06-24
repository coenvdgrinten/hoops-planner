Hoops Planner is a planning app for the tasks we do at our local basketball club 'BC Vido'. The app provides the planner of tasks with a nice UI that makes the usual puzzle of figuring who has to do which task a lot easier, and automatically tracks statistics of the people doing the tasks (amount of tasks done, etc.). The planner follows a set of rules so that invalid combinations are impossible.

To populate the app, the planner can import the season's game schedules and club member lists via a CSV/Excel upload, with the long-term goal of integrating directly with the Sportlink/NBB API to automate schedule synchronization.

---

## Tech Stack
- **Frontend:** React (lives in this repo alongside the backend — monorepo)
- **Backend:** Django REST API (Python)
- **Tooling:** uv (environment management), ruff (linting), ty (type checking)
- **Testing:** Full test suite for all logic components

---

## Task Types
The app differentiates between a couple of tasks:
- **Refereeing** — 2 or 1 needed, configurable per age category
- **Scorer** — Keeping live score of the game on a tablet; needed for all games
- **Timer** — Keeping live time and score on a physical scoreboard; needed for all games
- **24 Second Operator** — Operates the 24-second clock; configurable per team in settings (e.g., MSE1 needs it, MSE2 does not)

---

## Infrastructure
- Club has **2 basketball courts** — games can run simultaneously
- Games on different courts share the exact same time slot
- Consecutive time slots are ~2 hours apart

---

## Eligibility Rules
The basic rule set that invalidates someone from being able to do a task:
- The team the player is part of already has a home game at the same time
- The team the player is part of already has an away game on the same day
- For refereeing: The team the player is a part of is of a lower age than the team playing
- For refereeing: The game's level requires a specific referee certification/license tier, and the player does not hold it
- The player is already on a task for this game

**Coach Exemption:** Coaches are exempt from tasks entirely — they won't be suggested or required. However, if they volunteer for a task, they can still be assigned. Coaches should have a visible indicator in the UI.

---

## Task Counter & Multipliers
The app tracks a personal task counter per member. Configurable multipliers affect how a task contributes to this counter:
- Task assigned on a day the member has no game of their own: **2x multiplier** (counts as 2 toward their counter)

This incentivizes assigning tasks to members who are already at the gym for their own team's games.

---

## Candidate Suggestion Logic
When the user clicks a task slot to fill, the app suggests best candidates ranked by:

1. **Already at the gym** (strong priority) — the member's team has a home game in the time slot immediately before or after the task's slot. Games on different courts happen at the exact same time; consecutive slots are ~2 hours apart, so "immediately before/after" means the adjacent scheduled slot.
2. **Lowest effective task counter** (tie-breaker / secondary sort) — among eligible members, those with the lowest personal task counter are suggested first.

This minimizes extra travel time while distributing tasks evenly over the season.

---

## Additional Features
- **PDF Export** — export the task schedule for printing
- **Member View** — mobile-friendly, read-only web view where members can log in and check their upcoming assignments
- **Swap Requests** — if a member can't make a duty, they can initiate a swap request to trade slots with another eligible player, subject to planner approval
- **Statistics** — track and export performance stats per team and per individual
- **Reminders** — automated email/messaging reminders a few days before an assigned game
- **Authentication** — user accounts created from scratch; starts with a single admin user

---

## Phased Rollout
**Phase 1 (✅ Complete):** CSV import, interactive planner, eligibility rules, candidate suggestions
**Phase 2 (✅ Complete):** PDF export, member read-only view, statistics
**Phase 3:** Swap requests, reminders, Sportlink/NBB API integration

---

## Implementation Status

### Backend (Django)
- ✅ Database models (Team, Player, Season, Game, Task, TaskAssignment)
- ✅ Eligibility logic (all disqualification rules + coach exemption)
- ✅ Suggestion logic (at-gym priority + task counter tiebreaker)
- ✅ CSV import (schedules + members with upsert)
- ✅ REST API (serializers, viewsets, custom endpoints)
- ✅ CORS configuration for React dev server
- ✅ Statistics module (player stats, season stats, leaderboard, upcoming assignments)
- ✅ PDF export (reportlab, per-game task tables)
- ✅ 46 tests (21 eligibility + 13 suggestions + 11 importers + 1 placeholder)

### Frontend (React + TypeScript + Vite)
- ✅ TypeScript types matching API
- ✅ API layer with fetch wrappers
- ✅ SeasonSelector component
- ✅ ImportModal (schedule + members CSV import)
- ✅ Planner view with sorted game list
- ✅ GameCard with match details
- ✅ TaskCard with assignment/unassignment + candidate suggestions
- ✅ Statistics view (overview cards, task type breakdown, leaderboard)
- ✅ MemberView (player selector, upcoming assignments table)
- ✅ PDF export button
- ✅ CSS styling

### CI/CD
- ✅ Ruff linting (GitHub Actions)
- ✅ Ty type checking (GitHub Actions)
- ✅ Pytest (GitHub Actions)

---

## Example Home Day
A given home day might look like this:
- Vido X10-1 vs. Jumping Giants on Court 1
- Vido X14-2 vs. Achilles '71 on Court 2
- Vido VSE2 vs. BV Rush on Court 1
- Vido X14-1 vs. Attacus on Court 2
- Vido VSE1 vs. Trajanum on Court 1
- Vido M16-1 vs. Achilles '71 on Court 2
- Vido MSE1 vs. Tantalus on Court 1
- Vido M18-1 vs. Almonte on Court 2
- Vido MSE2 vs. Tantalus on Court 1

Provided a schedule of games, the user can start planning interactively. At first, all task slots are empty. When the user clicks a slot to fill, an interface opens showing all teams and their individual players, with ineligible ones indicated in red. A subtle number indicator shows the count of valid volunteers for the task. The app also automatically finds and suggests the best candidates based on the logic above.