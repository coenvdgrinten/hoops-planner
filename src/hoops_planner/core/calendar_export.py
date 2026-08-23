"""Calendar export (.ics) for the task schedule."""

from datetime import datetime, timedelta

from hoops_planner.core.models import Season, Task, TaskType

TASK_LABELS: dict[str, str] = {
    TaskType.REFEREE: "Fluiten",
    TaskType.SCORER: "Scoren",
    TaskType.TIMER: "Tijd",
    TaskType.SECOND_24_OPERATOR: "24-seconde",
}

# Default game duration: 2 hours
DEFAULT_GAME_DURATION = timedelta(hours=2)


def export_schedule_ics(season: Season) -> bytes:
    """Generate an .ics calendar file with one event per task slot."""
    games = list(season.games.all().order_by("date", "time", "court"))

    # Pre-fetch all tasks
    game_ids = [g.id for g in games]
    tasks = Task.objects.filter(game__id__in=game_ids).order_by(
        "game", "task_type", "slot_number"
    ).select_related("game")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Hoops Planner//Task Schedule//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for task in tasks:
        game = task.game
        dtstart = datetime.combine(game.date, game.time)
        dtend = dtstart + DEFAULT_GAME_DURATION
        label = TASK_LABELS.get(task.task_type, task.task_type)
        summary = f"{label} {game.own_team} vs {game.opponent}"

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"DTSTART:{dtstart.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND:{dtend.strftime('%Y%m%dT%H%M%S')}",
                f"SUMMARY:{summary}",
                f"LOCATION:{game.location or 'Den Ekkerman'} - Court {game.court}",
                "STATUS:CONFIRMED",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")

    content = "\r\n".join(lines)
    return content.encode("utf-8")
