"""CSV export for the task schedule (assignments)."""

import csv
import io
from typing import Any

from hoops_planner.core.models import Season, Task, TaskAssignment, TaskType

TASK_LABELS: dict[str, str] = {
    TaskType.REFEREE: "Referee",
    TaskType.SCORER: "Scorer",
    TaskType.TIMER: "Timer",
    TaskType.SECOND_24_OPERATOR: "24-sec Operator",
}


def export_schedule_csv(season: Season) -> str:
    """Generate a CSV of the task schedule (one row per task) for a season.

    Each row carries the game details, the task type/slot, and the assigned
    player (with their team). Unassigned tasks list an empty assigned player.
    Returns the CSV as a string.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow(
        [
            "date",
            "time",
            "court",
            "half",
            "game_type",
            "home_team",
            "away_team",
            "task_type",
            "slot",
            "assigned_player",
            "player_team",
        ]
    )

    games = season.games.all().order_by("date", "time", "court")
    for game in games:
        tasks = Task.objects.filter(game=game).order_by("task_type", "slot_number")
        if not tasks:
            continue
        for task in tasks:
            assignments = TaskAssignment.objects.filter(task=task).select_related(
                "player", "player__team"
            )
            if assignments:
                for assignment in assignments:
                    writer.writerow(_row(game, task, assignment))
            else:
                writer.writerow(_row(game, task, None))

    return buffer.getvalue()


def _row(game: Any, task: Any, assignment: TaskAssignment | None) -> list[str]:
    player_name = ""
    player_team = ""
    if assignment is not None and assignment.player is not None:
        player_name = assignment.player.full_name
        player_team = assignment.player.team.name if assignment.player.team else ""
    return [
        game.date.isoformat() if game.date else "",
        game.time.strftime("%H:%M") if game.time else "",
        game.court,
        game.half or "",
        game.game_type,
        game.home_team.name if game.home_team else "",
        game.away_team or "",
        TASK_LABELS.get(task.task_type, task.task_type),
        str(task.slot_number),
        player_name,
        player_team,
    ]
