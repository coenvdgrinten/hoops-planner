"""PDF export for the task schedule — HTML/CSS-based layout using WeasyPrint."""

import os
from collections import namedtuple
from datetime import date as date_type
from datetime import time as time_type
from pathlib import Path
from typing import Literal

from django.conf import settings
from django.db.models import Count, QuerySet
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

# PDF stylesheet lives in its own file for readability and independent review.
CSS_STYLES: str = (Path(__file__).parent / "pdf_styles.css").read_text()

AssignmentEntry = namedtuple(
    "AssignmentEntry", ["name", "team", "is_away_day", "task_id"]
)


def _is_own_team_game(player_team: Team | None, game: Game) -> bool:
    """True when the game is for a team the player belongs to.

    ``own_team`` is always the club team the game is for, so the player's team
    is involved only when it is the own_team.
    """
    if player_team is None:
        return False
    return game.own_team_id == player_team.id


def _build_assignment_lookup(
    tasks, assignments
) -> dict[tuple[int, str], list[AssignmentEntry]]:
    """Map (game_id, task_type) → list of assigned players with display info."""
    assigned: dict[tuple[int, str], list[AssignmentEntry]] = {}
    for t in tasks:
        for a in assignments:
            if a.task.id != t.id:
                continue
            name = a.player.full_name
            if t.task_type in (TaskType.SCORER, TaskType.TIMER):
                # Only label "Ouder van" when the task's own team is
                # parent_responsible AND the player is a member/coach of
                # that specific team.
                own_team = t.game.own_team
                if own_team.parent_responsible and own_team in a.player.all_teams:
                    name = f"Ouder van {a.player.full_name}"
            # Checked over the WHOLE season — the 2× rule depends only
            # on same-date games, so export scope can't change it.
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
            assigned.setdefault((t.game.id, t.task_type), []).append(
                AssignmentEntry(name, a.player.team.name, is_away_day, t.id)
            )
    return assigned


def export_schedule_pdf(
    season: Season,
    half: Literal["1", "2"] | None = None,
    game_ids: list[int] | None = None,
    full_season_stats: bool = False,
) -> bytes:
    """Generate a compact, date-grouped PDF of the task schedule.

    ``half`` ("1"/"2") or ``game_ids`` (explicit selection) restrict which
    games are rendered (issue #9); absent means the whole season.
    ``full_season_stats`` opts the summary sections into season-wide totals
    even when the rendered games are scoped.
    """
    html_content = _build_html(
        season, half=half, game_ids=game_ids, full_season_stats=full_season_stats
    )
    base_url = getattr(settings, "SITE_URL", "http://localhost:5173")
    html = HTML(string=html_content, base_url=base_url)
    return html.write_pdf(
        font_config=FontConfiguration(),
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


def _build_html(
    season: Season,
    half: Literal["1", "2"] | None = None,
    game_ids: list[int] | None = None,
    full_season_stats: bool = False,
) -> str:
    """Build the HTML content for the PDF.

    ``half`` / ``game_ids`` scope which games are rendered (issue #9);
    ``full_season_stats`` makes the summary sections cover the whole season
    even when the rendered games are scoped.
    """
    games_qs = season.games.all().order_by("half", "date", "time", "court")
    if game_ids is not None:
        games_qs = games_qs.filter(pk__in=game_ids)
    elif half:
        games_qs = games_qs.filter(half=half)
    games = list(games_qs)

    by_date: dict[date_type, list[Game]] = {}
    for game in games:
        by_date.setdefault(game.date, []).append(game)

    # Named ``rendered_game_ids`` so it doesn't shadow the ``game_ids`` param.
    rendered_game_ids = [g.id for g in games]
    tasks = Task.objects.filter(game__id__in=rendered_game_ids).order_by(
        "game", "task_type", "slot_number"
    )
    task_ids = [t.id for t in tasks]
    assignments = TaskAssignment.objects.filter(task__id__in=task_ids).select_related(
        "player", "player__team"
    )

    assigned = _build_assignment_lookup(tasks, assignments)

    max_referees = 0
    for t in tasks:
        if t.task_type == TaskType.REFEREE:
            max_referees = max(max_referees, t.slot_number)
    max_referees = max(max_referees, 2)

    has_24sec = any(t.task_type == TaskType.SECOND_24_OPERATOR for t in tasks)

    headers = ["Datum", "Tijd", "Thuis", "Uit", "Locatie"]
    for i in range(1, max_referees + 1):
        suffix = f" #{i}" if i > 1 else ""
        headers.append(f"Scheidsr{suffix}")
        headers.append("Team")
    headers.extend(["Scorer", "Team", "Timer", "Team"])
    if has_24sec:
        headers.extend(["24 sec", "Team"])

    logo_html = ""
    if os.path.exists(LOGO_PATH):
        logo_url = f"file://{LOGO_PATH.absolute()}"
        logo_html = f'<img src="{logo_url}" class="logo" alt="Logo">'

    club_name = SiteConfig.load().club_name
    club_html = f'<span class="club-name">{club_name}</span>' if club_name else ""

    # A scoped document states its scope in the title so a distributed file
    # is self-describing (issue #9).
    half_label = {"1": "First Half", "2": "Second Half"}.get(half or "")
    scope_label = half_label or ("Custom Selection" if game_ids is not None else "")
    title = f"Task Schedule — {season.name}" + (
        f" ({scope_label})" if scope_label else ""
    )

    html_parts = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        f"<style>{CSS_STYLES}</style>",
        "</head>",
        "<body>",
        f'<div class="header">{logo_html}{club_html}'
        f'<span class="title">{title}</span></div>',
    ]

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

        day_games = by_date[game_date]
        first_time = day_games[0].time
        if first_time.minute >= 30:
            setup_time = first_time.replace(minute=first_time.minute - 30)
        else:
            setup_time = first_time.replace(
                hour=(first_time.hour - 1) % 24,
                minute=first_time.minute + 30,
            )
        html_parts.append(
            f'<tr class="setup-row">'
            f"{_build_setup_row_html(setup_time, 'Opbouwen zaal', len(headers) - 2)}"
            f"</tr>"
        )

        for game in day_games:
            row = _build_game_row_html(game, assigned, max_referees, has_24sec)
            html_parts.append(f"<tr>{row}</tr>")

        cleanup_time = day_games[-1].time
        html_parts.append(
            f'<tr class="setup-row">'
            f"{_build_setup_row_html(cleanup_time, 'Afbouwen zaal', len(headers) - 2)}"
            f"</tr>"
        )

        html_parts.extend(["</tbody>", "</table>"])

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

    # Summaries follow the export scope by default; ``full_season_stats``
    # opts into season-wide totals (issue #9).
    stats_games = season.games.all() if full_season_stats else games_qs

    team_summary_html = _build_team_summary_html(season, stats_games)
    summary_html = _build_player_summary_html(season, stats_games)

    # Only force a page break when there is something to break to — a sparse
    # scope can leave both summaries empty, which must not yield a trailing
    # blank page.
    if team_summary_html or summary_html:
        html_parts.append('<div style="page-break-before: always"></div>')
    if team_summary_html:
        html_parts.append(team_summary_html)
    if summary_html:
        html_parts.append(summary_html)

    html_parts.append(
        f'<div class="footer">Generated on {date_type.today().strftime("%Y-%m-%d")} '
        f'• <a href="https://github.com/coenvdgrinten/hoops-planner">'
        f"Hoops Planner</a></div>"
    )

    html_parts.extend(["</body>", "</html>"])

    return "\n".join(html_parts)


def _build_game_row_html(
    game: Game,
    assigned: dict[tuple[int, str], list[AssignmentEntry]],
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


def _build_setup_row_html(time: time_type, label: str, col_count: int) -> str:
    """Build a gym setup/teardown row (not tied to a specific game).

    ``col_count`` is the number of columns the label spans after the Datum
    and Tijd cells (i.e. ``len(headers) - 2``).
    """
    cells = [
        '<td class="center"></td>',  # Datum (filled by date header)
        f'<td class="time">{time.strftime("%H:%M")}</td>',
        f'<td class="setup-label" colspan="{col_count}">{label}</td>',
    ]
    return "".join(cells)


def _build_team_summary_html(
    season: Season, games: QuerySet[Game] | None = None
) -> str:
    """Build a per-team total task count section.

    Mirrors the "NT" indicator in the UI: how many tasks each team's members
    have been assigned this season, giving context for fair distribution
    across differently-sized teams. Also shows the average tasks per member.

    ``games`` scopes which games' assignments are counted (issue #9);
    ``None`` means the whole season. Member counts stay roster-wide, so
    "Avg/Member" reads as the scoped load per full-time member.
    """
    game_ids = (
        games.values_list("pk", flat=True)
        if games is not None
        else season.games.all().values_list("pk", flat=True)
    )
    counts = {
        tid: n
        for tid, n in (
            TaskAssignment.objects.filter(task__game__id__in=game_ids)
            .values("player__team_id")
            .annotate(n=Count("id"))
            .values_list("player__team_id", "n")
        )
    }
    if not counts:
        return ""

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


def _build_player_summary_html(
    season: Season, games: QuerySet[Game] | None = None
) -> str:
    """Build player summary HTML sections, grouped by team."

    Instead of one flat alphabetical list, players are split into a section
    per team so each team's member statistics sit together. Includes an
    "Eff." column showing the multiplier-weighted total (2× when the
    player's team has no game that day), matching the app's fairness logic.

    ``games`` scopes which games' assignments are counted (issue #9);
    ``None`` means the whole season. Players with no assignments in scope
    simply don't appear — every number refers to what is visible.
    """
    game_ids = (
        games.values_list("pk", flat=True)
        if games is not None
        else season.games.all().values_list("pk", flat=True)
    )
    assignments = TaskAssignment.objects.filter(
        task__game__id__in=game_ids
    ).select_related("player", "player__team", "task__game")

    # Teams playing per date — over the WHOLE season (not scoped games),
    # since the 2× multiplier depends only on same-date games.
    date_teams: dict[date_type, set[int]] = {}
    for d, tid in Game.objects.filter(season=season).values_list("date", "own_team_id"):
        date_teams.setdefault(d, set()).add(tid)

    # Each player's responsible teams (own + coached).
    player_team_ids: dict[int, set[int]] = {}
    for p in Player.objects.all().prefetch_related("coached_teams"):
        player_team_ids[p.id] = {p.team_id} | {t.id for t in p.coached_teams.all()}

    player_counts: dict[tuple[int, str], dict[str, int]] = {}
    player_effective: dict[tuple[int, str], float] = {}
    for a in assignments:
        key = (a.player.team_id, a.player.full_name)
        task_label = TASK_LABELS.get(a.task.task_type, a.task.task_type)
        counts = player_counts.setdefault(key, {})
        counts[task_label] = counts.get(task_label, 0) + 1

        game_date = a.task.game.date
        my_teams = player_team_ids.get(a.player.id, {a.player.team_id})
        mult = 1 if my_teams & date_teams.get(game_date, set()) else 2
        player_effective[key] = player_effective.get(key, 0) + mult

    if not player_counts:
        return ""

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
