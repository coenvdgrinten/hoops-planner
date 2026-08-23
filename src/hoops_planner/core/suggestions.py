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

from django.db.models import Count

from hoops_planner.core.eligibility import evaluate_player_eligibility_batched
from hoops_planner.core.models import (
    Game,
    Player,
    Task,
    TaskAssignment,
    TaskType,
    Team,
)

# Team ordering for display (oldest to youngest), matching the MemberView.
CATEGORY_ORDER = ["MSE", "VSE", "M16", "X16", "X14", "X12", "X10"]

# Players whose team has a home game within this window are considered
# "already at the gym".
ADJACENT_TIME_WINDOW = dt.timedelta(hours=2)

# Credit (in effective-task units) given to a parent filling a scorer/timer
# slot for their own kid's team. It nudges parents up the ranking at equal
# load without making them unbeatable: a noticeably lighter non-parent can
# still outrank a heavily loaded parent.
PARENT_TASK_BONUS = 1.0

# Ranking-only surcharge for players who already work a task on the target
# day. Deliberately kept out of the effective task count itself, which must
# stay consistent with the statistics rule (tasks on a day one of the
# player's teams plays count single). It makes a same-day task weigh 3x in
# the ranking (1x counted + 2x penalty); without it, a player whose team
# plays later that day would outrank a free teammate despite already being
# double-booked for the evening.
SAME_DAY_TASK_PENALTY = 2.0


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
    all_players = list(Player.objects.all().select_related("team"))
    eligibility = evaluate_player_eligibility_batched(task, all_players)
    eligible = [p for p in all_players if eligibility[p.id][0]]
    if not eligible:
        return []

    info = _batch_position_and_count(eligible, task.game)

    # Rank key: players with an adjacent game first, then by effective task
    # count. Players who already work a task on the target day get a small
    # penalty so a free teammate outranks them at equal load — even when
    # their own team plays that day (which would otherwise count single).
    # Parents filling a scorer/timer slot for their own kid's team get a
    # bonus so they're preferred at equal load, but a lighter non-parent
    # can still outrank a heavily loaded parent.
    def _rank(p: Player) -> tuple[int, float]:
        position, count, has_same_day_task, boost_allowed = info[p.id]
        eff_position = position if boost_allowed else None
        if _is_parent_for_task(p, task):
            count -= PARENT_TASK_BONUS
        elif has_same_day_task:
            count += SAME_DAY_TASK_PENALTY
        return (0 if eff_position else 1, count)

    ranked = sorted(eligible, key=_rank)
    return ranked[:limit]


def get_candidate_details(
    task: Task,
    limit: int = 5,
) -> list[tuple[Player, float, str | None, str, bool]]:
    """Return candidate details with task count, at_gym flag, and suggestion reason.

    Each tuple is (player, effective_task_count, game_position, suggestion_reason,
    has_other_task_same_day). game_position is "before" | "after" | None.
    suggestion_reason explains why this player is suggested.
    """
    all_players = list(Player.objects.all().select_related("team"))
    eligibility = evaluate_player_eligibility_batched(task, all_players)
    eligible = [p for p in all_players if eligibility[p.id][0]]
    if not eligible:
        return []

    info = _batch_position_and_count(eligible, task.game)
    results: list[tuple[Player, float, str | None, str, bool]] = []
    for player in eligible:
        position, count, has_same_day_task, boost_allowed = info[player.id]
        eff_position = position if boost_allowed else None
        is_parent = _is_parent_for_task(player, task)
        reason = _get_suggestion_reason(eff_position, count, is_parent)
        results.append((player, count, eff_position, reason, has_same_day_task))

    # Sort: players with a game (before/after) first, then by count
    # (ascending). Players already working a task on the target day get a
    # small penalty; parents get a bonus so they're preferred at equal load,
    # but a lighter non-parent can still outrank a heavily loaded parent.
    # ``position`` here is already gated by the at-gym boost allowance.
    def _sort_key(
        entry: tuple[Player, float, str | None, str, bool],
    ) -> tuple[int, float]:
        player, count, position = entry[0], entry[1], entry[2]
        _, _, has_same_day_task, _boost_allowed = info[player.id]
        if _is_parent_for_task(player, task):
            count -= PARENT_TASK_BONUS
        elif has_same_day_task:
            count += SAME_DAY_TASK_PENALTY
        return (0 if position else 1, count)

    results.sort(key=_sort_key)
    return results[:limit]


def _batch_position_and_count(
    players: list[Player],
    game: Game,
) -> dict[int, tuple[str | None, float, bool, bool]]:
    """Compute (adjacent-game position, effective task count, same-day flag,
    at-gym boost allowed).

    Returns ``{player_id: (position, count, has_same_day_task, boost_allowed)}``
    where position is "before", "after" or None and ``has_same_day_task`` is
    True when the player already works a task on the target day. The count
    itself matches the statistics rule (tasks on a day one of the player's
    teams plays count single); the same-day flag is applied as a ranking-only
    penalty by the callers so the displayed task load stays honest.

    ``boost_allowed`` is False for members of a ``parent_responsible`` team
    when the target game is not one of their own teams' games — such parents
    are at the gym for their kid, but we don't want to recruit them onto
    other teams' games before/after it. Callers use it to gate the at-gym
    priority group; the raw position is kept for display surfaces.
    """
    if not players:
        return {}

    # --- Each player's responsible teams (own + coached) ---
    player_ids = [p.id for p in players]
    coached_map: dict[int, list[int]] = {}
    for row in (
        Player.objects.filter(id__in=player_ids)
        .prefetch_related("coached_teams")
        .values_list("id", "coached_teams__id")
    ):
        _, ct_id = row
        if ct_id is not None:
            coached_map.setdefault(row[0], []).append(ct_id)
    all_team_ids_by_player: dict[int, set[int]] = {
        p.id: {p.team_id} | set(coached_map.get(p.id, [])) for p in players
    }
    all_team_ids: set[int] = set().union(*all_team_ids_by_player.values())

    # Parenting-rule members (members of a parent_responsible team) only get
    # the "already at the gym" boost for their own teams' games, so they are
    # not recruited onto other teams' games before/after their kid's.
    parent_responsible_team_ids = set(
        Team.objects.filter(parent_responsible=True).values_list("id", flat=True)
    )

    # --- Adjacent home games for the "already at the gym" check ---
    game_dt = dt.datetime.combine(game.date, game.time)
    time_start = game_dt - ADJACENT_TIME_WINDOW
    time_end = game_dt + ADJACENT_TIME_WINDOW
    adjacent_games_qs = Game.objects.filter(
        own_team__id__in=list(all_team_ids),
        game_type=Game.GameType.HOME,
        date__gte=time_start.date(),
        date__lte=time_end.date(),
    ).order_by("time")
    adjacent_by_team: dict[int, Game] = {}
    for g in adjacent_games_qs:
        g_dt = dt.datetime.combine(g.date, g.time)
        if time_start <= g_dt <= time_end:
            if g.own_team_id not in adjacent_by_team:
                adjacent_by_team[g.own_team_id] = g

    def _position(player: Player) -> str | None:
        for tid in all_team_ids_by_player[player.id]:
            g = adjacent_by_team.get(tid)
            if g:
                return "before" if g.time < game.time else "after"
        return None

    def _boost_allowed(player: Player) -> bool:
        team_ids = all_team_ids_by_player[player.id]
        if not (team_ids & parent_responsible_team_ids):
            return True
        # Parenting-rule member: only boost for their own teams' games.
        return game.own_team_id in team_ids

    # --- Effective task counts ---
    assignments_by_player: dict[int, list[TaskAssignment]] = {}
    for a in TaskAssignment.objects.filter(player_id__in=player_ids).select_related(
        "task__game"
    ):
        assignments_by_player.setdefault(a.player_id, []).append(a)

    team_game_dates_map: dict[int, set[dt.date]] = {}
    if all_team_ids:
        for tid, d in Game.objects.filter(own_team_id__in=all_team_ids).values_list(
            "own_team_id", "date"
        ):
            team_game_dates_map.setdefault(tid, set()).add(d)

    def _count(player: Player) -> tuple[float, bool]:
        """Return (effective task count, has_a_task_on_the_target_day)."""
        assignments = assignments_by_player.get(player.id, [])
        player_team_game_dates: set[dt.date] = set()
        for tid in all_team_ids_by_player[player.id]:
            player_team_game_dates |= team_game_dates_map.get(tid, set())
        total = 0.0
        has_same_day_task = False
        for assignment in assignments:
            task_game_date = assignment.task.game.date
            if task_game_date in player_team_game_dates:
                multiplier = 1.0
            elif task_game_date == game.date:
                multiplier = 3.0
            else:
                multiplier = 2.0
            total += multiplier
            if task_game_date == game.date:
                has_same_day_task = True
        return total, has_same_day_task

    return {p.id: (_position(p), *_count(p), _boost_allowed(p)) for p in players}


def get_team_eligibility(task: Task) -> list[dict[str, Any]]:
    """Return all teams with their members, eligibility, and task counts.

    Each team dict contains:
    - team: Team instance
    - players: list of dicts with player, eligible, task_count, at_gym
    - eligible_count: number of eligible players in this team

    Batches every database access up front so the endpoint issues a handful of
    queries instead of one per player per rule.
    """
    game = task.game

    # --- Players (with team) and their eligibility against this task ---
    all_players = list(Player.objects.all().select_related("team"))
    eligibility = evaluate_player_eligibility_batched(task, all_players)

    # --- Teams, ordered oldest-to-youngest then by name ---
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

    # --- Position + effective count for every player, in a few queries ---
    info = _batch_position_and_count(all_players, game)

    # --- Teams that have a home game on the task's date ("at gym" day) ---
    teams_with_day_game = set(
        Game.objects.filter(
            own_team__in=all_teams,
            date=game.date,
        ).values_list("own_team_id", flat=True)
    )

    # --- Group players by team for display ---
    players_by_team: dict[int, list[Player]] = {}
    for p in all_players:
        players_by_team.setdefault(p.team_id, []).append(p)

    # --- Total assigned tasks per team (whole season) ---
    assignment_counts: dict[int, int] = {}
    for pid, n in (
        TaskAssignment.objects.values("player__team_id")
        .annotate(n=Count("id"))
        .values_list("player__team_id", "n")
    ):
        if pid is not None:
            assignment_counts[pid] = n

    results = []
    for team in all_teams:
        team_players = players_by_team.get(team.id)
        if not team_players:
            continue

        players = []
        for player in team_players:
            eligible, reason = eligibility[player.id]
            position, count, same_day, _boost_allowed = info[player.id]
            players.append(
                {
                    "player": player,
                    "eligible": eligible,
                    "ineligible_reason": reason,
                    "task_count": count,
                    "at_gym": position,
                    "has_same_day_task": same_day,
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
                "total_tasks": assignment_counts.get(team.id, 0),
            }
        )

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_parent_for_task(player: Player, task: Task) -> bool:
    """True when the player is a responsible adult for the task's own team.

    Applies only to SCORER/TIMER tasks on a team with ``parent_responsible``
    set — the situation where parents are expected to fill the slot for their
    kid's team. Used to give such parents a ranking bonus in suggestions.
    """
    if task.task_type not in (TaskType.SCORER, TaskType.TIMER):
        return False
    if not task.game.own_team.parent_responsible:
        return False
    return task.game.own_team in player.all_teams


def _get_suggestion_reason(
    position: str | None, _count: float, is_parent: bool = False
) -> str:
    """Return a human-readable suggestion reason."""
    if is_parent:
        return "Parent of this team"
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

    Tasks on days one of the player's teams (including coached ones) plays
    count 1x — the player is at the gym anyway. Tasks on the same day as
    ``game_date``, when none of the player's teams plays that day, count 3x
    to deprioritize players who already have a task that day. All other
    tasks (away days) count 2x.
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
        if task_game_date in team_game_dates:
            # One of the player's teams plays that day: they are at the gym
            # anyway, so the task counts single.
            multiplier = 1.0
        elif task_game_date == game_date:
            # Same day as the target game (and no own-team game that day):
            # double duty on a travel day.
            multiplier = 3.0
        else:
            multiplier = 2.0
        total += multiplier
    return total
