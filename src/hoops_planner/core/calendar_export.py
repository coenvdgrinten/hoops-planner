"""Calendar export (.ics) for the task schedule."""

from datetime import datetime, timedelta

from hoops_planner.core.models import Season, Task, TaskAssignment, TaskType

TASK_LABELS: dict[str, str] = {
    TaskType.REFEREE: "Referee",
    TaskType.SCORER: "Scorer",
    TaskType.TIMER: "Timer",
    TaskType.SECOND_24_OPERATOR: "24-sec Operator",
}

# Default game duration: 2 hours
DEFAULT_GAME_DURATION = timedelta(hours=2)


def export_schedule_ics(season: Season) -> bytes:
    """Generate an .ics calendar file for all games in a season."""
    games = list(season.games.all().order_by("date", "time", "court"))

    # Pre-fetch all tasks and assignments
    game_ids = [g.id for g in games]
    tasks = Task.objects.filter(game__id__in=game_ids).order_by(
        "game", "task_type", "slot_number"
    )
    task_ids = [t.id for t in tasks]
    assignments = TaskAssignment.objects.filter(task__id__in=task_ids).select_related(
        "player", "player__team"
    )

    # Build lookup: game_id -> list of (task_type_label, player_name)
    game_tasks: dict[int, list[tuple[str, str]]] = {}
    for t in tasks:
        for a in assignments:
            if a.task.id == t.id:
                name = a.player.full_name
                if t.task_type in (TaskType.SCORER, TaskType.TIMER):
                    if any(tr.parent_responsible for tr in a.player.all_teams):
                        name = f"Ouder van {a.player.full_name}"
                game_tasks.setdefault(t.game.id, []).append(
                    (TASK_LABELS.get(t.task_type, t.task_type), name)
                )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Hoops Planner//Task Schedule//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for game in games:
        dtstart = datetime.combine(game.date, game.time)
        dtend = dtstart + DEFAULT_GAME_DURATION
        tasks = game_tasks.get(game.id, [])

        description_parts = []
        for label, name in sorted(tasks):
            description_parts.append(f"{label}: {name}")
        description = (
            " | ".join(description_parts) if description_parts else "No tasks assigned"
        )

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"DTSTART:{dtstart.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND:{dtend.strftime('%Y%m%dT%H%M%S')}",
                f"SUMMARY:{game.own_team} vs {game.opponent}",
                f"DESCRIPTION:{description}",
                f"LOCATION:{game.location or 'Den Ekkerman'} - Court {game.court}",
                "STATUS:CONFIRMED",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")

    content = "\r\n".join(lines)
    return content.encode("utf-8")
