# Conflict indicators embedded in per-game payloads

A `GET /seasons/{id}/conflicts/` endpoint already exists and returns all conflicting assignments for a season. For surfacing conflicts in the planner UI we decided NOT to call it separately, but to embed a `conflict_reason` on each assignment inside the existing per-game `tasks_with_assignments` response (and a `conflict_count` in the season stats response).

Reason: the chips render from `tasks_with_assignments`, so co-located data refreshes automatically with the query invalidation the UI already performs after every mutation — a separate conflicts query would need its own invalidation in every mutation site and could transiently disagree with the chips. The dedicated `/conflicts/` endpoint stays available for season-wide consumers (e.g. future overview screens or exports). Both paths compute via the same shared helper in `eligibility.py`, so the rule set can never drift.
