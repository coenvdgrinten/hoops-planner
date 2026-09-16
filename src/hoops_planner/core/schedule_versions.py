"""Schedule versions — immutable snapshots of a season's task schedule.

A version captures the ENTIRE season (all halves) in a canonical, display-free
payload so any two versions stay comparable. Captured on export via
``?save_version=1&note=...``; see ``views.SeasonViewSet.export_pdf/csv``.

Design decisions (settled 2026-09-04, GOAL.md → Schedule Versions):
- Numbering: auto-increment per season (v1, v2, ...).
- Dedupe: SHA-256 over the normalized payload; if identical to the LATEST
  version, skip saving and tell the user (the response carries a message).
- Retention: keep all versions; no deletion UI.
- Payload carries stable entity ids AND names so later diffs survive
  renames/moves (needed by issue #7 "compare two versions").
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from django.db import transaction

from hoops_planner.core.models import Game, ScheduleVersion, Season, Task


@dataclass(frozen=True)
class SaveVersionResult:
    """Outcome of a save attempt.

    ``version_number`` is set when a new row was created; ``message`` is always
    set and safe to surface to the user (success or dedupe-skip).
    """

    saved: bool
    version_number: int | None
    message: str


def build_payload(season: Season) -> dict[str, Any]:
    """Build the canonical, display-free payload for a whole season.

    Shape::

        {
          "season": {"id": 1, "name": "2025-2026"},
          "games": [
            {
              "id": 10, "date": "2025-10-04", "time": "14:00", "court": "1",
              "half": "1", "game_type": "HOME", "location": "Den Ekkerman",
              "own_team": {"id": 1, "name": "Vido MSE1"},
              "opponent": "Tantalus",
              "tasks": [
                {
                  "id": 100, "task_type": "REFEREE", "slot_number": 1,
                  "optional": false,
                  "assignment": {"player_id": 7, "player_name": "Jane Smith",
                                 "team_id": 3, "team_name": "Vido X14-1"}
                }
              ]
            }
          ]
        }

    Every entity carries its id AND name(s); assignments are embedded in their
    task (a slot holds at most one assignment). Unassigned tasks carry
    ``"assignment": null``. No pre-rendered display labels.
    """
    games = (
        Game.objects.filter(season=season)
        .select_related("own_team")
        .order_by("date", "time", "court")
    )
    game_entries = []
    for game in games:
        tasks = (
            Task.objects.filter(game=game)
            .prefetch_related("assignments__player__team")
            .order_by("task_type", "slot_number")
        )
        task_entries = []
        for task in tasks:
            assignment = task.assignments.first()
            player = assignment.player if assignment else None
            team = player.team if player else None
            task_entries.append(
                {
                    "id": task.id,
                    "task_type": task.task_type,
                    "slot_number": task.slot_number,
                    "optional": task.optional,
                    "assignment": (
                        None
                        if player is None
                        else {
                            "player_id": player.id,
                            "player_name": player.full_name,
                            "team_id": team.id if team else None,
                            "team_name": team.name if team else None,
                        }
                    ),
                }
            )
        game_entries.append(
            {
                "id": game.id,
                "date": game.date.isoformat(),
                "time": game.time.strftime("%H:%M"),
                "court": game.court,
                "half": game.half,
                "game_type": game.game_type,
                "location": game.location,
                "own_team": {
                    "id": game.own_team.id,
                    "name": game.own_team.name,
                },
                "opponent": game.opponent,
                "tasks": task_entries,
            }
        )
    return {
        "season": {"id": season.id, "name": season.name},
        "games": game_entries,
    }


def content_hash(payload: dict[str, Any]) -> str:
    """SHA-256 over the normalized (sorted-keys, compact) JSON encoding."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def save_version(season: Season, note: str = "") -> SaveVersionResult:
    """Capture an immutable snapshot of the season's current schedule.

    Dedupes against the LATEST version only: if the payload hashes to the same
    value as the newest snapshot, nothing is stored and the result reports the
    existing number. Runs in a transaction so numbering never skips under
    concurrent saves (unique_together on (season, number) backstops it).
    """
    with transaction.atomic():
        latest = (
            ScheduleVersion.objects.filter(season=season)
            .order_by("-number")
            .first()
        )
        payload = build_payload(season)
        digest = content_hash(payload)

        if latest is not None and latest.content_hash == digest:
            return SaveVersionResult(
                saved=False,
                version_number=latest.number,
                # ASCII only: this message travels in a response header
                # (X-Schedule-Version-Message), where non-ASCII chars get
                # RFC 2047-encoded and would render as "=?utf-8?q?…".
                message=(
                    f"No changes since v{latest.number} - no new version saved."
                ),
            )

        number = (latest.number + 1) if latest else 1
        version = ScheduleVersion.objects.create(
            season=season,
            number=number,
            note=note.strip(),
            content_hash=digest,
            payload=payload,
        )
        return SaveVersionResult(
            saved=True,
            version_number=version.number,
            message=f"Saved schedule version v{version.number}.",
        )
