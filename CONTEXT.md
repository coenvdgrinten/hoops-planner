# Hoops Planner

Planning app for BC Vido: assigns club members to game-day tasks (referee, scorer, timer, 24-second operator) under eligibility rules, and tracks fairness statistics.

## Language

**Task**:
A single staffable slot on a game (e.g. "Referee 2", "Scorer"). Created from the team's staffing settings when the game is created; slots are never removed by later settings changes.
_Avoid_: duty, shift

**Assignment**:
The link of one player to one task slot. At most one assignment per slot.
_Avoid_: entry, booking

**Conflict**:
An existing assignment that no longer satisfies the eligibility rules after a roster or schedule change (member changed team, away game added on the same day, home game added at the same time, double-booking, exemption, referee age or certification). Conflicts are detected on read, not prevented on write.
_Avoid_: invalid entry, stale assignment, violation

**Eligibility**:
Whether a player may be assigned to a task right now, per the disqualification rules (own-team involvement, same-time home game, same-day away game, double-booking, exemption, referee age/certification).
_Avoid_: availability (that word is reserved for the away-day availability view)

**Time slot**:
A date + time pair; games on different courts share a time slot exactly.
_Avoid_: round, session

**Half**:
First or second half of a season; games are ordered by half, then date, then time.
