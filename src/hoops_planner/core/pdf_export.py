"""PDF export for the task schedule — HTML/CSS-based layout using WeasyPrint."""

import os
from datetime import date as date_type
from pathlib import Path

from django.conf import settings
from django.db.models import Count
from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration
from weasyprint.urls import URLFetcher, URLFetcherResponse

from hoops_planner.core.eligibility import AGE_CATEGORY_ORDER
from hoops_planner.core.models import (
    Game,
    Player,
    Season,
    SiteConfig,
    Task,
    TaskAssignment,
    TaskType,
    Team,
)


def _team_age_key(team: Team) -> tuple[int, str]:
    """Sort key ordering teams by ascending age, then name.

    Reuses ``AGE_CATEGORY_ORDER`` (youngest first) so the PDF matches the
    app's canonical age ordering; unknown categories sort last.
    """
    try:
        idx = AGE_CATEGORY_ORDER.index(team.age_category)
    except ValueError:
        idx = len(AGE_CATEGORY_ORDER)
    return (idx, team.name)


TASK_LABELS: dict[str, str] = {
    TaskType.REFEREE: "Referee",
    TaskType.SCORER: "Scorer",
    TaskType.TIMER: "Timer",
    TaskType.SECOND_24_OPERATOR: "24-sec Operator",
}

# Logo path (relative to project root)
LOGO_PATH = Path(settings.BASE_DIR).parent / "media" / "assets" / "club-logo.png"


def _is_own_team_game(player_team: Team | None, game: Game) -> bool:
    """True when the game is for a team the player belongs to.

    ``own_team`` is always the club team the game is for, so the player's team
    is involved only when it is the own_team.
    """
    if player_team is None:
        return False
    return game.own_team_id == player_team.id


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

.club-name {
    font-size: 11pt;
    font-weight: 700;
    color: #f97316;
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

.day-table {
    page-break-inside: avoid;
}

th {
    background: #ffedd5;
    color: #ea580c;
    font-weight: 600;
    font-size: 8pt;
    text-align: center;
    padding: 4pt 3pt;
    border: 0.5pt solid #ccc;
    border-bottom: 1.5pt solid #ea580c;
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
    border-top: 0.75pt solid #ea580c;
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
    color: #e57373;
    text-align: center;
    background: #fff5f5 !important;
}

.summary-title {
    font-size: 12pt;
    font-weight: 600;
    margin: 12pt 0 6pt 0;
    color: #1a1a2e;
}

.team-row {
    page-break-after: avoid;
}

.team-row td {
    background: #fff7ed;
    color: #ea580c;
    font-weight: 600;
    text-align: left;
    border-top: 0.75pt solid #ea580c;
}

.summary-table th {
    background: #ffedd5;
    color: #ea580c;
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
    color: #ea580c;
    text-decoration: none;
    font-size: 7pt;
    vertical-align: middle;
}

.calendar-link:hover {
    text-decoration: underline;
}

.away-day {
    color: #d32f2f;
    font-weight: 600;
}

.parent {
    color: #2e7d32;
}

.footer {
    text-align: center;
    font-size: 8pt;
    color: #666;
    margin-top: 12pt;
    padding-top: 6pt;
    border-top: 0.5pt solid #ddd;
}
.footer a {
    color: #f97316;
    text-decoration: none;
}

.legend-box {
    border: 0.75pt solid #e0e0e0;
    border-radius: 4pt;
    padding: 5pt 10pt;
    margin: 8pt 0;
    font-size: 7.5pt;
    color: #555;
    display: flex;
    gap: 14pt;
}
.legend-box .item { display: flex; align-items: center; gap: 4pt; }
.legend-box .swatch {
    display: inline-block;
    width: 8pt;
    height: 8pt;
    border-radius: 2pt;
}
.legend-box .swatch-red { background: #d32f2f; }
.legend-box .swatch-pink { background: #fff5f5; border: 0.5pt solid #e57373; }
.legend-box .swatch-parent { background: #e8f5e9; border: 0.5pt solid #66bb6a; }
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

    # Build lookup: (game_id, task_type) -> [(name, team, is_away_day)]
    assigned: dict[tuple[int, str], list[tuple[str, str, bool, int]]] = {}
    for t in tasks:
        for a in assignments:
            if a.task.id == t.id:
                key = (t.game.id, t.task_type)
                name = a.player.full_name
                if t.task_type in (TaskType.SCORER, TaskType.TIMER):
                    # Only label "Ouder van" when the task's own team is
                    # parent_responsible AND the player is a member/coach of
                    # that specific team. A VSE member coaching X12 must not be
                    # labelled a parent for an unrelated team's slot.
                    own_team = t.game.own_team
                    if own_team.parent_responsible and own_team in a.player.all_teams:
                        name = f"Ouder van {a.player.full_name}"
                # Away day = player's team has no game on this date → 2x multiplier
                player_team = a.player.team
                is_away_day = (
                    player_team is not None
                    and not _is_own_team_game(player_team, t.game)
                    and not Game.objects.filter(
                        season=t.game.season,
                        date=t.game.date,
                        own_team=player_team,
                    )
                    .exclude(pk=t.game.id)
                    .exists()
                )
                assigned.setdefault(key, []).append(
                    (name, a.player.team.name, is_away_day, t.id)
                )

    # Determine max referees needed
    max_referees = 0
    for t in tasks:
        if t.task_type == TaskType.REFEREE:
            max_referees = max(max_referees, t.slot_number)
    max_referees = max(max_referees, 2)

    has_24sec = any(t.task_type == TaskType.SECOND_24_OPERATOR for t in tasks)

    # Build header row
    headers = ["Datum", "Tijd", "Thuis", "Uit", "Locatie"]
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

    # Club name from site config (empty string if not set)
    club_name = SiteConfig.load().club_name
    club_html = f'<span class="club-name">{club_name}</span>' if club_name else ""

    html_parts = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        f"<style>{CSS_STYLES}</style>",
        "</head>",
        "<body>",
        f'<div class="header">{logo_html}{club_html}'
        f'<span class="title">Task Schedule — {season.name}</span></div>',
    ]

    # Legend box
    legend_items = (
        ("swatch-red", "Away day (counts 2\u00d7)"),
        ("swatch-pink", "Unfilled slot"),
        ("swatch-parent", '"Ouder van" = parent'),
    )
    items_html = "".join(
        f'<span class="item"><span class="swatch {cls}"></span> {txt}</span>'
        for cls, txt in legend_items
    )
    html_parts.append(f'<div class="legend-box">{items_html}</div>')

    # Shared column header row, reused in every per-day table so the labels
    # repeat on each page and survive a page break inside a long day.
    header_cells = "".join(f"<th>{h}</th>" for h in headers)

    # One table per day. ``page-break-inside: avoid`` keeps each day together
    # so a date is never split across two pages (a day taller than a page
    # still breaks, but its header stays with the first games).
    for game_date in sorted(by_date.keys()):
        date_str = game_date.strftime("%d-%m-%Y")
        html_parts.append('<table class="day-table">')
        html_parts.append(f"<thead><tr>{header_cells}</tr></thead>")
        html_parts.append("<tbody>")
        html_parts.append(f'<tr class="date-row"><td colspan="2">{date_str}</td>')
        for _ in range(2, len(headers)):
            html_parts.append("<td></td>")
        html_parts.append("</tr>")

        for game in by_date[game_date]:
            row = _build_game_row_html(game, assigned, max_referees, has_24sec)
            html_parts.append(f"<tr>{row}</tr>")

        html_parts.extend(["</tbody>", "</table>"])

    # Force page break before summaries
    html_parts.append('<div style="page-break-before: always"></div>')

    # Team summary (total tasks per team)
    team_summary_html = _build_team_summary_html(season)
    if team_summary_html:
        html_parts.append(team_summary_html)

    # Player summary
    summary_html = _build_player_summary_html(season)
    html_parts.append(summary_html)

    # Footer
    from datetime import date as _date

    html_parts.append(
        f'<div class="footer">Generated on {_date.today().strftime("%Y-%m-%d")} '
        f'• <a href="https://github.com/coenvdgrinten/hoops-planner">'
        f"Hoops Planner</a></div>"
    )

    html_parts.extend(["</body>", "</html>"])

    return "\n".join(html_parts)


def _build_game_row_html(
    game: Game,
    assigned: dict[tuple[int, str], list[tuple[str, str, bool, int]]],
    max_referees: int,
    has_24sec: bool,
) -> str:
    """Build a single HTML row for a game."""
    time_str = game.time.strftime("%H:%M")
    # Thuis/Uit reflect the actual home/away of the fixture. ``own_team`` is
    # always the club team, so for away games the opponent is at home.
    if game.game_type == Game.GameType.HOME:
        home = game.own_team.name
        away = game.opponent
    else:
        home = game.opponent
        away = game.own_team.name

    cells = [
        '<td class="center"></td>',  # Datum (filled by date header)
        f'<td class="time">{time_str}</td>',
        f'<td class="bold">{home}</td>',
        f"<td>{away}</td>",
        f'<td class="center">{game.location or "Den Ekkerman"}</td>',
    ]

    base_url = getattr(settings, "SITE_URL", "http://localhost:5173")

    def _cell(
        name: str, team: str, is_away: bool, task_id: int | None = None
    ) -> tuple[str, str]:
        away_cls = " away-day" if is_away else ""
        name_cls = "center" + away_cls
        if name.startswith("Ouder van"):
            name_cls += " parent"
        ics_url = f"{base_url}/api/game_ics/?game_id={game.id}"
        if task_id:
            ics_url += f"&task_id={task_id}"
        return (
            f'<td class="{name_cls}">{name} '
            f'<a href="{ics_url}" class="calendar-link">Calendar</a></td>',
            f'<td class="team{away_cls}">{team}</td>',
        )

    # Referee columns
    for i in range(1, max_referees + 1):
        key = (game.id, TaskType.REFEREE)
        players = assigned.get(key, [])
        if i <= len(players):
            name, team, is_away, task_id = players[i - 1]
            cells.extend(_cell(name, team, is_away, task_id))
        else:
            cells.append('<td class="unassigned">—</td>')
            cells.append("<td></td>")

    # Scorer
    scorer_key = (game.id, TaskType.SCORER)
    scorers = assigned.get(scorer_key, [])
    if scorers:
        name, team, is_away, task_id = scorers[0]
        cells.extend(_cell(name, team, is_away, task_id))
    else:
        cells.append('<td class="unassigned">—</td>')
        cells.append("<td></td>")

    # Timer
    timer_key = (game.id, TaskType.TIMER)
    timers = assigned.get(timer_key, [])
    if timers:
        name, team, is_away, task_id = timers[0]
        cells.extend(_cell(name, team, is_away, task_id))
    else:
        cells.append('<td class="unassigned">—</td>')
        cells.append("<td></td>")

    # 24-sec operator
    if has_24sec:
        op_key = (game.id, TaskType.SECOND_24_OPERATOR)
        ops = assigned.get(op_key, [])
        if ops:
            name, team, is_away, task_id = ops[0]
            cells.extend(_cell(name, team, is_away, task_id))
        else:
            cells.append('<td class="unassigned">—</td>')
            cells.append("<td></td>")

    return "".join(cells)


def _build_team_summary_html(season: Season) -> str:
    """Build a per-team total task count section.

    Mirrors the "NT" indicator in the UI: how many tasks each team's members
    have been assigned this season, giving context for fair distribution
    across differently-sized teams. Also shows the average tasks per member.
    """
    counts = {
        tid: n
        for tid, n in (
            TaskAssignment.objects.filter(task__game__season=season)
            .values("player__team_id")
            .annotate(n=Count("id"))
            .values_list("player__team_id", "n")
        )
    }
    if not counts:
        return ""

    # Member count per team.
    member_counts = {
        tid: n
        for tid, n in (
            Player.objects.filter(team_id__in=counts.keys())
            .values("team_id")
            .annotate(n=Count("id"))
            .values_list("team_id", "n")
        )
    }

    teams = sorted(Team.objects.filter(id__in=counts.keys()), key=_team_age_key)
    rows = []
    for team in teams:
        total = counts[team.id]
        members = member_counts.get(team.id, 0)
        avg = f"{total / members:.1f}" if members else "—"
        rows.append(
            f"<tr><td>{team.name}</td><td>{total}</td>"
            f"<td>{members}</td><td>{avg}</td></tr>"
        )

    html_parts = [
        '<div class="summary-title">Team Summary</div>',
        '<table class="summary-table">',
        "<thead>",
        "<tr>",
        "<th>Team</th>",
        "<th>Total Tasks</th>",
        "<th>Members</th>",
        "<th>Avg/Member</th>",
        "</tr>",
        "</thead>",
        "<tbody>",
    ]
    html_parts.extend(rows)
    html_parts.extend(["</tbody>", "</table>"])
    return "\n".join(html_parts)


def _build_player_summary_html(season: Season) -> str:
    """Build player summary HTML sections, grouped by team.

    Instead of one flat alphabetical list, players are split into a section
    per team so each team's member statistics sit together. Includes an
    "Eff." column showing the multiplier-weighted total (2× when the
    player's team has no game that day), matching the app's fairness logic.
    """
    assignments = TaskAssignment.objects.filter(
        task__game__season=season
    ).select_related("player", "player__team", "task__game")

    # --- Effective-load data (same rule as statistics.get_player_stats) ---
    # Which teams play on which date.
    date_teams: dict[date_type, set[int]] = {}
    for d, tid in Game.objects.filter(season=season).values_list("date", "own_team_id"):
        date_teams.setdefault(d, set()).add(tid)

    # Each player's responsible teams (own + coached).
    player_team_ids: dict[int, set[int]] = {}
    for p in Player.objects.all().prefetch_related("coached_teams"):
        player_team_ids[p.id] = {p.team_id} | {t.id for t in p.coached_teams.all()}

    # Count assignments per player per task type AND effective total.
    player_counts: dict[tuple[int, str], dict[str, int]] = {}
    player_effective: dict[tuple[int, str], float] = {}
    for a in assignments:
        key = (a.player.team_id, a.player.full_name)
        task_label = TASK_LABELS.get(a.task.task_type, a.task.task_type)
        counts = player_counts.setdefault(key, {})
        counts[task_label] = counts.get(task_label, 0) + 1

        # Effective: 1 if any of the player's teams plays that day, else 2.
        game_date = a.task.game.date
        my_teams = player_team_ids.get(a.player.id, {a.player.team_id})
        mult = 1 if my_teams & date_teams.get(game_date, set()) else 2
        player_effective[key] = player_effective.get(key, 0) + mult

    if not player_counts:
        return ""

    # Group players by their team
    by_team: dict[int, list[tuple[str, dict[str, int]]]] = {}
    for (team_id, name), counts in player_counts.items():
        by_team.setdefault(team_id, []).append((name, counts))

    teams = sorted(Team.objects.filter(id__in=by_team.keys()), key=_team_age_key)
    labels = list(TASK_LABELS.values())
    col_count = len(labels) + 3  # Player + task-type columns + Total + Eff.

    # One continuous table for all teams; each team is introduced by a
    # full-width separator row so the summary stays compact (no repeated
    # column headers per team) and flows cleanly across pages.
    html_parts = ['<div class="summary-title">Player Summary</div>']
    html_parts.append('<table class="summary-table">')
    html_parts.append("<thead><tr><th>Player</th>")
    for label in labels:
        html_parts.append(f"<th>{label}</th>")
    html_parts.append("<th>Total</th><th>Eff.</th></tr></thead><tbody>")
    for team in teams:
        members = sorted(by_team[team.id], key=lambda x: x[0].lower())
        html_parts.append(
            f'<tr class="team-row"><td colspan="{col_count}">{team.name}</td></tr>'
        )
        for name, counts in members:
            cells = [f"<td>{name}</td>"]
            total = 0
            for label in labels:
                count = counts.get(label, 0)
                total += count
                cells.append(f"<td>{count}</td>")
            eff = player_effective.get((team.id, name), float(total))
            eff_display = int(eff) if eff == int(eff) else f"{eff:.1f}"
            cells.append(f"<td>{total}</td>")
            cells.append(f"<td>{eff_display}</td>")
            html_parts.append(f"<tr>{''.join(cells)}</tr>")
    html_parts.extend(["</tbody>", "</table>"])

    return "\n".join(html_parts)
