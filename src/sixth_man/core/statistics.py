"""Statistics computation for players and seasons."""

from collections import defaultdict
from datetime import date
from typing import Any

from sixth_man.core.models import Player, Season, Task, TaskAssignment, TaskType


def get_player_stats(
    player: Player,
    season: Season | None = None,
) -> dict[str, Any]:
    """Compute statistics for a single player, optionally filtered by season.

    Returns:
        {
            "total_tasks": int,
            "effective_tasks": float,  # with 2x multiplier for away days
            "by_type": {TASK_TYPE: count, ...},
            "games_with_own_team": int,
            "games_without_own_team": int,
        }
    """
    # Get all assignments for this player
    assignments = player.assignments.select_related("task__game")
    if season:
        assignments = assignments.filter(task__game__season=season)

    # Pre-fetch all dates the player's team has a home game (single query)
    player_team = player.team
    team_game_dates = set(player_team.home_games.values_list("date", flat=True))

    total = 0
    effective = 0.0
    by_type: dict[str, int] = defaultdict(int)
    games_with_own_team = 0
    games_without_own_team = 0

    for assignment in assignments:
        task = assignment.task
        game = task.game
        total += 1
        by_type[task.task_type] += 1

        # Check if player's team has a game on this day
        has_own_game = game.date in team_game_dates

        if has_own_game:
            games_with_own_team += 1
            effective += 1.0
        else:
            games_without_own_team += 1
            effective += 2.0  # 2x multiplier for away days

    return {
        "total_tasks": total,
        "effective_tasks": effective,
        "by_type": dict(by_type),
        "games_with_own_team": games_with_own_team,
        "games_without_own_team": games_without_own_team,
    }


def get_season_stats(season: Season) -> dict[str, Any]:
    """Compute aggregate statistics for a season.

    Returns:
        {
            "total_games": int,
            "total_task_slots": int,
            "total_assignments": int,
            "fill_rate": float,  # assignments / task_slots
            "by_task_type": {TASK_TYPE: {"slots": int, "filled": int}, ...},
            "per_team": {team_name: {"games": int, "assignments": int}, ...},
        }
    """
    games = season.games.all()
    total_games = games.count()

    # All task slots in this season
    task_slots = Task.objects.filter(game__season=season)
    total_task_slots = task_slots.count()

    # All assignments in this season
    assignments = TaskAssignment.objects.filter(
        task__game__season=season
    ).select_related("player", "player__team", "task")
    total_assignments = assignments.count()

    fill_rate = total_assignments / total_task_slots if total_task_slots > 0 else 0.0

    # By task type
    by_task_type: dict[str, dict[str, Any]] = {}
    for task_type in TaskType.values:
        slots = Task.objects.filter(game__season=season, task_type=task_type).count()
        filled = TaskAssignment.objects.filter(
            task__game__season=season, task__task_type=task_type
        ).count()
        by_task_type[task_type] = {"slots": slots, "filled": filled}

    # Per team
    per_team: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"games": 0, "assignments": 0}
    )
    for game in games:
        team_name = game.home_team.name
        per_team[team_name]["games"] += 1

    for assignment in assignments:
        team_name = assignment.player.team.name
        per_team[team_name]["assignments"] += 1

    return {
        "total_games": total_games,
        "total_task_slots": total_task_slots,
        "total_assignments": total_assignments,
        "fill_rate": round(fill_rate * 100, 1),
        "by_task_type": by_task_type,
        "per_team": dict(per_team),
    }


def get_upcoming_assignments(
    player: Player,
    after: date | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Get upcoming task assignments for a player.

    Returns:
        List of dicts with game info and task type.
    """
    from datetime import date as date_type

    if after is None:
        after = date_type.today()

    assignments = (
        player.assignments.select_related("task__game", "task__game__home_team")
        .filter(task__game__date__gte=after)
        .order_by("task__game__date", "task__game__time", "task__task_type")[:limit]
    )

    result = []
    for a in assignments:
        game = a.task.game
        result.append(
            {
                "game_date": game.date.isoformat(),
                "game_time": game.time.strftime("%H:%M"),
                "home_team": game.home_team.name,
                "away_team": game.away_team,
                "court": game.court,
                "task_type": a.task.task_type,
                "slot_number": a.task.slot_number,
            }
        )

    return result


def get_leaderboard(
    season: Season,
    top: int = 10,
) -> list[dict[str, Any]]:
    """Get leaderboard of players by effective task count.

    Returns:
        List of dicts with player info and stats, sorted by effective_tasks desc.
    """
    players = Player.objects.filter(is_coach=False).select_related("team")
    leaderboard: list[dict[str, Any]] = []

    for player in players:
        stats = get_player_stats(player, season)
        if stats["total_tasks"] == 0:
            continue
        leaderboard.append(
            {
                "player_id": player.id,
                "player_name": player.full_name,
                "team": player.team.name,
                "total_tasks": stats["total_tasks"],
                "effective_tasks": stats["effective_tasks"],
                "by_type": stats["by_type"],
            }
        )

    leaderboard.sort(key=lambda x: x["effective_tasks"], reverse=True)
    return leaderboard[:top]
