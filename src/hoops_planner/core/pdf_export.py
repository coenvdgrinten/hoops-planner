"""PDF export for the task schedule — HTML/CSS-based layout using WeasyPrint."""

import os
from datetime import date as date_type
from pathlib import Path

from django.conf import settings
from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration
from weasyprint.urls import URLFetcher, URLFetcherResponse

from hoops_planner.core.models import Game, Season, Task, TaskAssignment, TaskType

TASK_LABELS: dict[str, str] = {
    TaskType.REFEREE: "Referee",
    TaskType.SCORER: "Scorer",
    TaskType.TIMER: "Timer",
    TaskType.SECOND_24_OPERATOR: "24-sec Operator",
}

# Logo path (relative to project root)
LOGO_PATH = Path(settings.BASE_DIR).parent / "media" / "assets" / "club-logo.png"

# CSS for the PDF
CSS_STYLES = """
@page {
    size: A4 landscape;
    margin: 15mm;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 9pt;
    color: #1a1a2e;
    margin: 0;
    padding: 0;
}

.header {
    display: flex;
    align-items: center;
    gap: 10mm;
    margin-bottom: 8pt;
}

.logo {
    width: 25mm;
    height: auto;
}

.title {
    font-size: 14pt;
    font-weight: 600;
    color: #1a1a2e;
}

table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    border-radius: 6pt;
    overflow: hidden;
    margin-bottom: 12pt;
    box-shadow: 0 1pt 3pt rgba(0,0,0,0.08);
}

th {
    background: #e6f5ed;
    color: #016c30;
    font-weight: 600;
    font-size: 8pt;
    text-align: center;
    padding: 4pt 3pt;
    border: 0.5pt solid #ccc;
    border-bottom: 1.5pt solid #016c30;
}

th:first-child {
    border-radius: 4pt 0 0 0;
}

th:last-child {
    border-radius: 0 4pt 0 0;
}

.date-row {
    background: #e8e8e8;
    font-weight: 600;
    font-size: 9pt;
    padding: 3pt 3pt;
    border: 0.5pt solid #ccc;
    border-top: 0.75pt solid #016c30;
}

td {
    padding: 2pt 3pt;
    border: 0.5pt solid #eeeeee;
    text-align: left;
    vertical-align: middle;
    font-size: 8pt;
}

td.center {
    text-align: center;
}

td.bold {
    font-weight: 600;
}

td.time {
    text-align: center;
    font-variant-numeric: tabular-nums;
}

td.team {
    text-align: center;
}

tr:nth-child(even) td {
    background: #f8f9fc;
}

tr.date-row td {
    background: #e8e8e8 !important;
}

td.unassigned {
    font-style: italic;
    color: #aaaaaa;
    text-align: center;
}

.summary-title {
    font-size: 12pt;
    font-weight: 600;
    margin: 12pt 0 6pt 0;
    color: #1a1a2e;
}

.summary-table th {
    background: #e6f5ed;
    color: #016c30;
}

.summary-table td {
    text-align: center;
}

.summary-table td:first-child {
    text-align: left;
}

.summary-table td:last-child {
    font-weight: 600;
}

.calendar-link {
    color: #016c30;
    text-decoration: none;
    font-size: 7pt;
    vertical-align: middle;
}

.calendar-link:hover {
    text-decoration: underline;
}

.footer {
    text-align: center;
    font-size: 8pt;
    color: #666;
    margin-top: 12pt;
    padding-top: 6pt;
    border-top: 0.5pt solid #ddd;
}
"""


def export_schedule_pdf(season: Season) -> bytes:
    """Generate a compact, date-grouped PDF of the task schedule."""
    html_content = _build_html(season)
    # Use SITE_URL as base so relative links resolve to absolute URLs
    base_url = getattr(settings, "SITE_URL", "http://localhost:5173")
    html = HTML(string=html_content, base_url=base_url)
    font_config = FontConfiguration()
    # Use a custom URL fetcher that doesn't actually fetch external URLs
    # (WeasyPrint strips links if it can't resolve the URL)
    return html.write_pdf(
        font_config=font_config,
        url_fetcher=NoFetchURLFetcher(),
        uncompressed_pdf=True,
    )


class NoFetchURLFetcher(URLFetcher):
    """URL fetcher that returns empty responses for external URLs,
    preventing WeasyPrint from stripping links it can't fetch."""

    def fetch(self, url, headers=None):
        if url.startswith("http"):
            return URLFetcherResponse(url, body=b"", status=200)
        return super().fetch(url, headers)


def _build_html(season: Season) -> str:
    """Build the HTML content for the PDF."""
    games = list(season.games.all().order_by("half", "date", "time", "court"))

    # Group games by date
    by_date: dict[date_type, list[Game]] = {}
    for game in games:
        by_date.setdefault(game.date, []).append(game)

    # Pre-fetch all tasks and assignments
    game_ids = [g.id for g in games]
    tasks = Task.objects.filter(game__id__in=game_ids).order_by(
        "game", "task_type", "slot_number"
    )
    task_ids = [t.id for t in tasks]
    assignments = TaskAssignment.objects.filter(task__id__in=task_ids).select_related(
        "player", "player__team"
    )

    # Build lookup: (game_id, task_type) -> [(name, team)]
    assigned: dict[tuple[int, str], list[tuple[str, str]]] = {}
    for t in tasks:
        for a in assignments:
            if a.task.id == t.id:
                key = (t.game.id, t.task_type)
                name = a.player.full_name
                if t.task_type in (TaskType.SCORER, TaskType.TIMER):
                    if any(tr.parent_responsible for tr in a.player.all_teams):
                        name = f"Ouder van {a.player.team.name}"
                assigned.setdefault(key, []).append((name, a.player.team.name))

    # Determine max referees needed
    max_referees = 0
    for t in tasks:
        if t.task_type == TaskType.REFEREE:
            max_referees = max(max_referees, t.slot_number)
    max_referees = max(max_referees, 2)

    has_24sec = any(t.task_type == TaskType.SECOND_24_OPERATOR for t in tasks)

    # Build header row
    headers = ["Datum", "Tijd", "Thuis", "Uit"]
    for i in range(1, max_referees + 1):
        suffix = f" #{i}" if i > 1 else ""
        headers.append(f"Scheidsr{suffix}")
        headers.append("Team")
    headers.extend(["Scorer", "Team", "Timer", "Team"])
    if has_24sec:
        headers.extend(["24 sec", "Team"])

    # Logo
    logo_html = ""
    if os.path.exists(LOGO_PATH):
        logo_url = f"file://{LOGO_PATH.absolute()}"
        logo_html = f'<img src="{logo_url}" class="logo" alt="Logo">'

    html_parts = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        f"<style>{CSS_STYLES}</style>",
        "</head>",
        "<body>",
        f'<div class="header">{logo_html}'
        f'<span class="title">Task Schedule — {season.name}</span></div>',
        "<table>",
        "<thead>",
        "<tr>",
    ]

    for h in headers:
        html_parts.append(f"<th>{h}</th>")

    html_parts.extend(["</tr>", "</thead>", "<tbody>"])

    for game_date in sorted(by_date.keys()):
        # Date header row — keep with following game rows
        date_str = game_date.strftime("%d-%m-%Y")
        html_parts.append(
            f'<tr class="date-row" style="page-break-inside: avoid">'
            f'<td colspan="2">{date_str}</td>'
        )
        for _ in range(2, len(headers)):
            html_parts.append("<td></td>")
        html_parts.append("</tr>")

        # Game rows — keep each game row together
        for game in by_date[game_date]:
            html_parts.append(
                f'<tr style="page-break-inside: avoid">'
                f"{_build_game_row_html(game, assigned, max_referees, has_24sec)}"
                f"</tr>"
            )

    html_parts.extend(["</tbody>", "</table>"])

    # Player summary
    summary_html = _build_player_summary_html(season)
    html_parts.append(summary_html)

    # Footer
    from datetime import date as _date
    html_parts.append(
        f'<div class="footer">Generated on {_date.today().strftime("%Y-%m-%d")} '
        f'• <a href="https://github.com/coenvdgrinten/hoops-planner">github.com/coenvdgrinten/hoops-planner</a></div>'
    )

    html_parts.extend(["</body>", "</html>"])

    return "\n".join(html_parts)


def _build_game_row_html(
    game: Game,
    assigned: dict[tuple[int, str], list[tuple[str, str]]],
    max_referees: int,
    has_24sec: bool,
) -> str:
    """Build a single HTML row for a game."""
    time_str = game.time.strftime("%H:%M")
    home = game.home_team.name
    away = game.away_team

    cells = [
        '<td class="center"></td>',  # Datum (filled by date header)
        f'<td class="time">{time_str}</td>',
        f'<td class="bold">{home}</td>',
        f"<td>{away}</td>",
    ]

    # Calendar event link for this game
    ics_url = f"{getattr(settings, 'SITE_URL', 'http://localhost:5173')}/api/game_ics/?game_id={game.id}"

    # Referee columns
    for i in range(1, max_referees + 1):
        key = (game.id, TaskType.REFEREE)
        players = assigned.get(key, [])
        if i <= len(players):
            name, team = players[i - 1]
            cells.append(
                f'<td class="center">{name} '
                f'<a href="{ics_url}" class="calendar-link">Calendar</a></td>'
            )
            cells.append(f'<td class="team">{team}</td>')
        else:
            cells.append('<td class="unassigned">—</td>')
            cells.append("<td></td>")

    # Scorer
    scorer_key = (game.id, TaskType.SCORER)
    scorers = assigned.get(scorer_key, [])
    if scorers:
        name, team = scorers[0]
        cells.append(
            f'<td class="center">{name} '
            f'<a href="{ics_url}" class="calendar-link">Calendar</a></td>'
        )
        cells.append(f'<td class="team">{team}</td>')
    else:
        cells.append('<td class="unassigned">—</td>')
        cells.append("<td></td>")

    # Timer
    timer_key = (game.id, TaskType.TIMER)
    timers = assigned.get(timer_key, [])
    if timers:
        name, team = timers[0]
        cells.append(
            f'<td class="center">{name} '
            f'<a href="{ics_url}" class="calendar-link">Calendar</a></td>'
        )
        cells.append(f'<td class="team">{team}</td>')
    else:
        cells.append('<td class="unassigned">—</td>')
        cells.append("<td></td>")

    # 24-sec operator
    if has_24sec:
        op_key = (game.id, TaskType.SECOND_24_OPERATOR)
        ops = assigned.get(op_key, [])
        if ops:
            name, team = ops[0]
            cells.append(
                f'<td class="center">{name} '
                f'<a href="{ics_url}" class="calendar-link">Calendar</a></td>'
            )
            cells.append(f'<td class="team">{team}</td>')
        else:
            cells.append('<td class="unassigned">—</td>')
            cells.append("<td></td>")

    return "".join(cells)


def _build_player_summary_html(season: Season) -> str:
    """Build player summary HTML section."""
    assignments = TaskAssignment.objects.filter(
        task__game__season=season
    ).select_related("player", "player__team", "task")

    # Count assignments per player per task type
    player_counts: dict[str, dict[str, int]] = {}
    for a in assignments:
        name = a.player.full_name
        if name not in player_counts:
            player_counts[name] = {}
        task_label = TASK_LABELS.get(a.task.task_type, a.task.task_type)
        player_counts[name][task_label] = player_counts[name].get(task_label, 0) + 1

    if not player_counts:
        return ""

    # Sort by last name
    sorted_players = sorted(player_counts.keys(), key=lambda x: x.lower())

    html_parts = [
        '<div class="summary-title">Player Summary</div>',
        '<table class="summary-table">',
        "<thead>",
        "<tr>",
        "<th>Player</th>",
    ]

    for label in TASK_LABELS.values():
        html_parts.append(f"<th>{label}</th>")

    html_parts.extend(["<th>Total</th>", "</tr>", "</thead>", "<tbody>"])

    for name in sorted_players:
        counts = player_counts[name]
        total = 0
        cells = [f"<td>{name}</td>"]
        for label in TASK_LABELS.values():
            count = counts.get(label, 0)
            total += count
            cells.append(f"<td>{count}</td>")
        cells.append(f"<td>{total}</td>")
        html_parts.append(f"<tr>{''.join(cells)}</tr>")

    html_parts.extend(["</tbody>", "</table>"])

    return "\n".join(html_parts)
