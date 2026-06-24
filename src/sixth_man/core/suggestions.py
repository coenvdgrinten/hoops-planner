"""Task assignment suggestions based on eligibility and fairness.

The suggestion algorithm ranks eligible players by:
1. Already at the gym (strong priority) — the player's team has a home
   game within the adjacent time window (default 2 hours) before or
   after the task's game.
2. Lowest effective task counter (tie-breaker) — among eligible players,
   those with the lowest personal task counter are suggested first.
"""

import datetime as dt

from sixth_man.core.eligibility import get_eligible_players
from sixth_man.core.models import Game, Player, Task

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

    # Separate players who are already at the gym.
    at_gym = []
    not_at_gym = []
    for player in eligible:
        if _player_already_at_gym(player, task.game):
            at_gym.append(player)
        else:
            not_at_gym.append(player)

    # Sort each group by effective task count.
    at_gym.sort(key=lambda p: _effective_task_count(p))
    not_at_gym.sort(key=lambda p: _effective_task_count(p))

    # Prefer players at the gym, then fall back to others.
    ranked = at_gym + not_at_gym
    return ranked[:limit]


def get_candidate_details(
    task: Task,
    limit: int = 5,
) -> list[tuple[Player, float, bool]]:
    """Return candidate details with task count and at_gym flag.

    Each tuple is (player, effective_task_count, already_at_gym).
    """
    eligible = get_eligible_players(task)
    results: list[tuple[Player, float, bool]] = []
    for player in eligible:
        at_gym = _player_already_at_gym(player, task.game)
        count = _effective_task_count(player)
        results.append((player, count, at_gym))

    # Sort: at_gym first (descending), then by count (ascending).
    results.sort(key=lambda x: (-x[2], x[1]))
    return results[:limit]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _player_already_at_gym(player: Player, game: Game) -> bool:
    """Check if the player's team has a home game within the adjacent time window.

    A player is considered "already at the gym" if their team has a home
    game on the same date within ADJACENT_TIME_WINDOW (default 2 hours)
    before or after the task's game time.
    """
    game_dt = dt.datetime.combine(game.date, game.time)
    time_start = game_dt - ADJACENT_TIME_WINDOW
    time_end = game_dt + ADJACENT_TIME_WINDOW

    return Game.objects.filter(
        home_team=player.team,
        game_type=Game.GameType.HOME,
        date=game.date,
        time__gte=time_start.time(),
        time__lte=time_end.time(),
    ).exists()


def _effective_task_count(player: Player) -> float:
    """Calculate the player's effective task count.

    Tasks assigned on days the player has no game get a 2x multiplier.
    """
    assignments = player.assignments.select_related("task__game").all()
    total = 0.0
    for assignment in assignments:
        game = assignment.task.game
        # Check if player's team has a game on the same day.
        has_game_on_day = Game.objects.filter(
            home_team=player.team,
            date=game.date,
        ).exists()
        multiplier = 1.0 if has_game_on_day else 2.0
        total += multiplier
    return total
