"""PDF export for the task schedule."""

from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from sixth_man.core.models import Season, Task, TaskAssignment, TaskType

TASK_LABELS: dict[str, str] = {
    TaskType.REFEREE: "Referee",
    TaskType.SCORER: "Scorer",
    TaskType.TIMER: "Timer",
    TaskType.SECOND_24_OPERATOR: "24-sec Operator",
}

# Styles
STYLE_HEADER = "Header"
STYLE_NORMAL = "Normal"
STYLE_SMALL = "Small"

STYLES = {
    STYLE_HEADER: {
        "fontName": "Helvetica-Bold",
        "fontSize": 14,
        "leading": 16,
        "spaceAfter": 6,
    },
    STYLE_NORMAL: {
        "fontName": "Helvetica",
        "fontSize": 9,
        "leading": 11,
    },
    STYLE_SMALL: {
        "fontName": "Helvetica",
        "fontSize": 8,
        "leading": 10,
    },
}


def export_schedule_pdf(season: Season) -> bytes:
    """Generate a PDF of the task schedule for a season.

    Returns raw PDF bytes.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    elements = _build_elements(season, STYLES)
    doc.build(elements)
    return buffer.getvalue()


def _build_elements(season: Season, styles: dict[str, Any]) -> list[Any]:
    """Build the list of platypus elements for the PDF."""
    base_styles = getSampleStyleSheet()
    for name, config in styles.items():
        base_styles.add(ParagraphStyle(name=name, **config))

    elements: list[Any] = []

    # Title
    title_text = f"Task Schedule — {season.name}"
    elements.append(Paragraph(title_text, base_styles[STYLE_HEADER]))
    elements.append(Spacer(1, 6 * mm))

    # Games sorted by date+time
    games = list(season.games.all().order_by("date", "time", "court"))

    for game in games:
        elements.append(_game_header(game, styles))
        elements.append(_task_table(game, styles))
        elements.append(Spacer(1, 4 * mm))

    return elements


def _game_header(game, styles: dict[str, Any]) -> Paragraph:
    from datetime import datetime

    date_str = datetime.combine(game.date, game.time).strftime("%a %d %b %H:%M")
    match_str = f"{game.home_team.name} vs {game.away_team}"
    meta_str = f"{date_str}  •  Court {game.court}"
    title = f"{match_str}  •  {meta_str}"
    return Paragraph(title, ParagraphStyle(
        "GameHeader",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        spaceAfter=2,
    ))


def _task_table(game, styles: dict[str, Any]) -> Table:
    """Create a table of tasks and assigned players for a game."""
    tasks = Task.objects.filter(game=game).order_by("task_type", "slot_number")

    # Pre-fetch all assignments for these tasks
    task_ids = [t.id for t in tasks]
    assignments = TaskAssignment.objects.filter(
        task__id__in=task_ids
    ).select_related("player")

    # Build lookup: task_id -> [player_names]
    assigned: dict[int, list[str]] = {}
    for a in assignments:
        assigned.setdefault(a.task.id, []).append(a.player.full_name)

    # Table data
    headers = ["Task", "Assigned"]
    header_style = ParagraphStyle(
        "ColHeader",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
    )
    data = [
        [
            Paragraph(h, header_style)
            for h in headers
        ]
    ]

    for task in tasks:
        label = TASK_LABELS.get(task.task_type, task.task_type)
        if task.slot_number > 1:
            label = f"{label} #{task.slot_number}"

        players = assigned.get(task.id, [])
        player_text = ", ".join(players) if players else "<i>unassigned</i>"

        data.append([
            Paragraph(label, styles[STYLE_SMALL]),
            Paragraph(player_text, styles[STYLE_SMALL]),
        ])

    # Table styling
    table = Table(data, colWidths=[50 * mm, 100 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))

    return table
