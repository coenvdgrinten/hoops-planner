"""Task assignment suggestions based on eligibility and fairness.

The suggestion algorithm ranks eligible players by:
1. Already at the gym (strong priority) — the player's team has a home
   game within the adjacent time window (default 2 hours) before or
   after the task's game.
2. Lowest effective task counter (tie-breaker) — among eligible players,
   those with the lowest personal task counter are suggested first.
"""

import datetime as dt
from typing import Any

from hoops_planner.core.eligibility import get_eligible_players
from hoops_planner.core.models import (
    Game,
    Player,
    Task,
    TaskAssignment,
    Team,
)

# Team ordering for display (oldest to youngest), matching the MemberView.
CATEGORY_ORDER = ["MSE", "VSE", "M16", "X16", "X14", "X12", "X10"]

# Players whose team has a home game within this window are considered
# "already at the gym".
ADJACENT_TIME_WINDOW = dt.timedelta(hours=2)


def suggest_candidates(
    task: Task,
    limit: int = 5,
) -> list[Player]:
    """Return the best candidate players for a task.

    Parameters
    ----------
    task : Task
        The task slot to fill.
    limit : int
        Maximum number of candidates to return.

    Returns
    -------
    list[Player]
        Ranked list of eligible players.
    """
    eligible = get_eligible_players(task)
    if not eligible:
        return []

    # Separate players who have an adjacent game.
    has_game = []
    no_game = []
    for player in eligible:
        if _player_game_position(player, task.game):
            has_game.append(player)
        else:
            no_game.append(player)

    # Sort each group by effective task count (penalizes same-day tasks).
    has_game.sort(key=lambda p: _effective_task_count(p, task.game.date))
    no_game.sort(key=lambda p: _effective_task_count(p, task.game.date))

    # Prefer players with an adjacent game, then fall back to others.
    ranked = has_game + no_game
    return ranked[:limit]


def get_candidate_details(
    task: Task,
    limit: int = 5,
) -> list[tuple[Player, float, str | None, str]]:
    """Return candidate details with task count, at_gym flag, and suggestion reason.

    Each tuple is (player, effective_task_count, game_position, suggestion_reason).
    game_position is "before" | "after" | None.
    suggestion_reason explains why this player is suggested.
    """
    eligible = get_eligible_players(task)
    results: list[tuple[Player, float, str | None, str]] = []
    for player in eligible:
        position = _player_game_position(player, task.game)
        count = _effective_task_count(player, task.game.date)
        reason = _get_suggestion_reason(position, count)
        results.append((player, count, position, reason))

    # Sort: players with a game (before/after) first, then by count (ascending).
    results.sort(key=lambda x: (0 if x[2] else 1, x[1]))
    return results[:limit]


def get_team_eligibility(task: Task) -> list[dict[str, Any]]:
    """Return all teams with their members, eligibility, and task counts.

    Each team dict contains:
    - team: Team instance
    - players: list of dicts with player, eligible, task_count, at_gym
    - eligible_count: number of eligible players in this team

    Optimized: batches all DB queries to avoid N+Q per player.
    """
    from hoops_planner.core.eligibility import (
        get_ineligibility_reason,
        is_eligible,
    )

    game = task.game

    # --- Batch 1: fetch all players with team pre-selected ---
    all_players = list(Player.objects.all().select_related("team"))

    # --- Batch 2: fetch all teams ---
    all_teams = Team.objects.all().order_by("name")
    all_teams = sorted(
        all_teams,
        key=lambda t: (
            CATEGORY_ORDER.index(t.age_category)
            if t.age_category in CATEGORY_ORDER
            else 999,
            t.name,
        ),
    )

    # --- Batch 3: collect all team IDs players are responsible for ---
    all_team_ids: set[int] = set()
    for p in all_players:
        all_team_ids.add(p.team_id)
        # We need coached_teams too – prefetch them
    # Re-fetch players with coached_teams prefetched
    player_coached = {
        p.id: [ct.id for ct in p.coached_teams.all()]
        for p in Player.objects.filter(
            id__in=[p.id for p in all_players]
        ).prefetch_related("coached_teams")
    }

    # Build all_teams set per player (own + coached)
    player_all_team_ids: dict[int, set[int]] = {}
    for p in all_players:
        ids = {p.team_id} | set(player_coached.get(p.id, []))
        player_all_team_ids[p.id] = ids

    # --- Batch 4: pre-compute adjacent games for "at gym" check ---
    game_dt = dt.datetime.combine(game.date, game.time)
    time_start = game_dt - ADJACENT_TIME_WINDOW
    time_end = game_dt + ADJACENT_TIME_WINDOW
    all_team_ids_list = list(all_team_ids)
    adjacent_games_qs = Game.objects.filter(
        own_team__id__in=all_team_ids_list,
        game_type=Game.GameType.HOME,
        date__gte=time_start.date(),
        date__lte=time_end.date(),
    ).order_by("time")
    # Map team_id -> first adjacent game
    adjacent_by_team: dict[int, Game] = {}
    for g in adjacent_games_qs:
        g_dt = dt.datetime.combine(g.date, g.time)
        if time_start <= g_dt <= time_end:
            if g.own_team_id not in adjacent_by_team:
                adjacent_by_team[g.own_team_id] = g

    def _player_game_position_batched(player: Player) -> str | None:
        for tid in player_all_team_ids[player.id]:
            g = adjacent_by_team.get(tid)
            if g:
                return "before" if g.time < game.time else "after"
        return None

    # --- Batch 5: pre-compute effective task counts ---
    # Fetch all assignments with game info
    all_assignments = TaskAssignment.objects.filter(
        player__in=[p.id for p in all_players]
    ).select_related("task__game")
    assignments_by_player: dict[int, list[TaskAssignment]] = {}
    for a in all_assignments:
        assignments_by_player.setdefault(a.player_id, []).append(a)

    # Fetch all game dates for all teams
    team_game_dates_map: dict[int, set[dt.date]] = {}
    for tid in all_team_ids:
        team_game_dates_map[tid] = set(
            Game.objects.filter(own_team_id=tid).values_list("date", flat=True)
        )

    def _effective_task_count_batched(player: Player) -> float:
        assignments = assignments_by_player.get(player.id, [])
        player_team_game_dates = set()
        for tid in player_all_team_ids[player.id]:
            player_team_game_dates |= team_game_dates_map.get(tid, set())
        total = 0.0
        for assignment in assignments:
            task_game_date = assignment.task.game.date
            if task_game_date == game.date:
                multiplier = 3.0
            elif task_game_date in player_team_game_dates:
                multiplier = 1.0
            else:
                multiplier = 2.0
            total += multiplier
        return total

    # --- Batch 6: pre-compute team_at_gym_day for each team ---
    teams_with_day_game = set(
        Game.objects.filter(
            own_team__in=all_teams,
            date=game.date,
        ).values_list("own_team_id", flat=True)
    )

    # --- Build results ---
    results = []
    for team in all_teams:
        team_players = [p for p in all_players if p.team == team]
        if not team_players:
            continue

        players = []
        for player in team_players:
            eligible = is_eligible(player, task)
            reason = get_ineligibility_reason(player, task)
            position = _player_game_position_batched(player)
            count = _effective_task_count_batched(player)
            players.append(
                {
                    "player": player,
                    "eligible": eligible,
                    "ineligible_reason": reason,
                    "task_count": count,
                    "at_gym": position,
                }
            )

        # Sort players by name
        players.sort(key=lambda p: p["player"].full_name)

        eligible_count = sum(1 for p in players if p["eligible"])
        results.append(
            {
                "team": team,
                "players": players,
                "eligible_count": eligible_count,
                "at_gym_day": team.id in teams_with_day_game,
            }
        )

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_suggestion_reason(position: str | None, _count: float) -> str:
    """Return a human-readable suggestion reason."""
    if position == "before":
        return "Already at the gym (game before)"
    elif position == "after":
        return "Already at the gym (game after)"
    else:
        return "Lowest task load"


def _player_game_position(player: Player, game: Game) -> str | None:
    """Determine if the player's team game is before or after the task's game.

    Returns "before" if the player's team plays before the task's game,
    "after" if they play after, or None if no adjacent game exists.
    """
    game_dt = dt.datetime.combine(game.date, game.time)
    time_start = game_dt - ADJACENT_TIME_WINDOW
    time_end = game_dt + ADJACENT_TIME_WINDOW

    # Query the adjacent date range to handle cross-midnight windows,
    # then filter by time within that range to stay within the window.
    candidates = Game.objects.filter(
        own_team__in=player.all_teams,
        game_type=Game.GameType.HOME,
        date__gte=time_start.date(),
        date__lte=time_end.date(),
    ).order_by("time")

    # Find the first candidate whose datetime falls within the window.
    adjacent_game = None
    for g in candidates:
        g_dt = dt.datetime.combine(g.date, g.time)
        if time_start <= g_dt <= time_end:
            adjacent_game = g
            break

    if adjacent_game is None:
        return None
    return "before" if adjacent_game.time < game.time else "after"


def _effective_task_count(player: Player, game_date: dt.date) -> float:
    """Calculate the player's effective task count.

    Tasks assigned on days the player has no game get a 2x multiplier.
    Tasks assigned on the same day as `game_date` get a 3x multiplier
    to deprioritize players who already have a task that day.
    """
    assignments = player.assignments.select_related("task__game").all()
    # Pre-fetch all dates any of the player's teams has a game.
    team_game_dates = set(
        Game.objects.filter(own_team__in=player.all_teams).values_list(
            "date", flat=True
        )
    )
    total = 0.0
    for assignment in assignments:
        task_game_date = assignment.task.game.date
        if task_game_date == game_date:
            multiplier = 3.0
        elif task_game_date in team_game_dates:
            multiplier = 1.0
        else:
            multiplier = 2.0
        total += multiplier
    return total
