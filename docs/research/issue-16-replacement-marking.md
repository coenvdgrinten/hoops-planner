# Issue 16: Marking tasks that need replacements

The “Existing behavior” section records the pre-implementation state. The task flag, mark/clear actions, assignment auto-resolution, season filter, planner controls, task-chip marker, and season overview have since been implemented.

## Issue

Issue [#16, “Mark certain tasks as needing replacement(s)”](https://github.com/coenvdgrinten/hoops-planner/issues/16) describes a member who cannot perform an assigned task and has not found a teammate to replace them. The planner needs a visible way to track that outstanding follow-up.

## Existing behavior

- The staffing unit is a `Task`: one role/slot on a game. An `Assignment` connects a player to a task. The glossary documents at most one assignment per slot. See [`CONTEXT.md`](../../CONTEXT.md) and [`models.py`](../../src/hoops_planner/core/models.py#L238).
- Task slots are created from team staffing requirements. Required and optional referee slots are distinct; `Task.optional` is not a workflow status. See [`importers.py`](../../src/hoops_planner/core/importers.py#L180).
- There is no persisted replacement-needed state. Assignment conflicts are calculated separately and mean an assignment became invalid after roster or schedule changes. See [`serializers.py`](../../src/hoops_planner/core/serializers.py#L135) and [`CONTEXT.md`](../../CONTEXT.md).
- The planner shows unfilled, optional, filled, and conflict states on task chips. Ordinary unfilled slots do not indicate that a member has explicitly called off. See [`GameCard.tsx`](../../frontend/src/components/GameCard.tsx#L160).
- Season statistics count assigned slots as filled and required unassigned slots as open. A replacement flag should not be confused with those counts. See [`statistics.py`](../../src/hoops_planner/core/statistics.py#L238).
- The game task response already returns tasks with their assignments. Existing ADR guidance favors embedding per-task indicators in that payload; a season-wide overview may need an additional filtered endpoint. See [`0001-conflicts-embedded-in-game-payloads.md`](../adr/0001-conflicts-embedded-in-game-payloads.md).

## Proposal

Add a persisted `needs_replacement` boolean to `Task`, defaulting to `false`. A task slot is the right scope: games can have several independently staffed tasks, and an assignment represents the person currently responsible. Keep this flag separate from optionality and assignment conflicts.

In the planner, make the flag easy to set and clear from the task’s assignment panel, show a distinct marker on the task chip, and provide a season-level “Needs replacement” overview that links back to each marked slot. Include the flag in both task serializers and the frontend task types. This keeps individual game cards in sync through the existing task query while giving the coordinator the cross-schedule action list requested by the issue.

When a confirmed call-off is marked, remove the unavailable member’s assignment so the schedule does not keep presenting them as responsible. Keep the replacement flag after removing the assignment, distinguishing it from an ordinary unfilled slot. Clear the flag when a replacement is assigned. Do not have the generic “clear all assignments” action mark slots as needing replacements; that action can be used for other reasons.

## Decisions to confirm before implementation

1. **Keep former assignee history?** The minimal proposal removes the assignment and does not retain who called off. If that history is needed, add an explicit history/replacement record rather than treating a current assignment as historical.
2. **Extra details?** The issue does not request a reason, contact, or audit trail; defer these unless the coordinator needs them.
3. **Resolution behavior:** This proposal clears the marker on successful assignment. If an assignment may be made provisionally, keep an explicit “resolve” action instead.

## Sources

- [GitHub issue #16](https://github.com/coenvdgrinten/hoops-planner/issues/16)
- [`CONTEXT.md`](../../CONTEXT.md)
- [`models.py`](../../src/hoops_planner/core/models.py#L238)
- [`importers.py`](../../src/hoops_planner/core/importers.py#L180)
- [`serializers.py`](../../src/hoops_planner/core/serializers.py#L102)
- [`statistics.py`](../../src/hoops_planner/core/statistics.py#L238)
- [`views.py`](../../src/hoops_planner/core/views.py#L494)
- [`types.ts`](../../frontend/src/types.ts#L55)
- [`GameCard.tsx`](../../frontend/src/components/GameCard.tsx#L160)
- [`0001-conflicts-embedded-in-game-payloads.md`](../adr/0001-conflicts-embedded-in-game-payloads.md)
