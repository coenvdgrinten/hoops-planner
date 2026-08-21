"""Eligibility checks for task assignments."""

from typing import Any

from hoops_planner.core.models import (
    Game,
    Player,
    Season,
    Task,
    TaskAssignment,
    TaskType,
    Team,
)

# Ordering of age categories for comparison (lower index = younger).
AGE_CATEGORY_ORDER = [
    "X10",
    "X12",
    "X14",
    "X16",
    "M16",
    "M18",
    "M22",
    "VSE",
    "MSE",
]


def is_eligible(player: Player, task: Task) -> bool:
    """Check if a player is eligible for a task.

    Returns False if any disqualification rule applies.
    """
    return not get_ineligibility_reason(player, task)


def get_ineligibility_reason(player: Player, task: Task) -> str | None:
    """Return the reason a player is ineligible, or None if eligible."""
    if player.is_exempt:
        return "Exempt from task assignments"
    if _already_assigned_to_game(player, task.game):
        return "Already assigned to this game"
    if _already_assigned_at_same_time(player, task.game):
        return "Already assigned to another task at this time"
    if _team_has_home_game_at_same_time(player, task.game):
        return "Team has a home game at the same time"
    if _team_has_away_game_on_same_day(player, task.game):
        return "Team has an away game on the same day"
    if _player_team_involved_in_game(player, task.game, task.task_type):
        return "Cannot be assigned to own team's game"
    if task.task_type == TaskType.REFEREE:
        if _player_team_is_lower_age_than_game_team(player, task.game):
            return "Player's team is younger than game team"
        if _player_lacks_required_referee_certification(player, task.game):
            return "Missing required referee certification"
    return None


def get_eligible_players(task: Task) -> list[Player]:
    """Return all eligible players for a task."""
    all_players = Player.objects.all()
    return [p for p in all_players if is_eligible(p, task)]


def get_eligible_players_with_indicator(task: Task) -> list[tuple[Player, bool]]:
    """Return all eligible players with an eligibility indicator.

    Each tuple is (player, is_eligible). Coaches are included and can be
    assigned voluntarily.
    """
    all_players = Player.objects.all()
    return [(p, is_eligible(p, task)) for p in all_players]


def evaluate_player_eligibility_batched(
    task: Task,
    players: list[Player],
) -> dict[int, tuple[bool, str | None]]:
    """Evaluate eligibility for many players against one task in a few queries.

    Returns ``{player_id: (is_eligible, ineligible_reason_or_None)}``.

    This produces byte-for-byte the same reasons as :func:`get_ineligibility_reason`
    (same checks, same order, same messages) but batches every database access
    up front instead of firing a query per player per rule. It is the fast path
    used by the suggestion endpoints; the single-player helpers above remain the
    source of truth for write-time validation.
    """
    game = task.game

    # --- Batch 1: every team's age category (for the referee age check) ---
    age_by_team: dict[int, str] = dict(
        Team.objects.values_list("id", "age_category")
    )

    # --- Batch 2: each player's responsible teams (own + coached) ---
    player_ids = [p.id for p in players]
    coached_map: dict[int, list[int]] = {}
    if player_ids:
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

    # --- Batch 3: games that disqualify by schedule ---
    home_same_time_ids = set(
        Game.objects.filter(
            game_type=Game.GameType.HOME,
            date=game.date,
            time=game.time,
        )
        .exclude(pk=game.pk)
        .values_list("own_team_id", flat=True)
    )
    away_same_day_ids = set(
        Game.objects.filter(
            game_type=Game.GameType.AWAY,
            date=game.date,
        ).values_list("own_team_id", flat=True)
    )

    # --- Batch 4: existing assignments that disqualify by double-booking ---
    assigned_to_game_ids = set(
        TaskAssignment.objects.filter(task__game=game).values_list(
            "player_id", flat=True
        )
    )
    assigned_same_time_ids = set(
        TaskAssignment.objects.filter(
            task__game__date=game.date,
            task__game__time=game.time,
        )
        .exclude(task__game=game)
        .values_list("player_id", flat=True)
    )

    game_own_team_id = game.own_team_id
    game_order = _age_category_index(game.own_team.age_category)
    is_referee = task.task_type == TaskType.REFEREE
    parent_exception = (
        task.task_type in (TaskType.SCORER, TaskType.TIMER)
        and game.own_team.parent_responsible
    )

    result: dict[int, tuple[bool, str | None]] = {}
    for p in players:
        team_ids = all_team_ids_by_player[p.id]

        if p.is_exempt:
            result[p.id] = (False, "Exempt from task assignments")
            continue
        if p.id in assigned_to_game_ids:
            result[p.id] = (False, "Already assigned to this game")
            continue
        if p.id in assigned_same_time_ids:
            result[p.id] = (False, "Already assigned to another task at this time")
            continue
        if team_ids & home_same_time_ids:
            result[p.id] = (False, "Team has a home game at the same time")
            continue
        if team_ids & away_same_day_ids:
            result[p.id] = (False, "Team has an away game on the same day")
            continue
        if game_own_team_id in team_ids and not parent_exception:
            result[p.id] = (False, "Cannot be assigned to own team's game")
            continue
        if is_referee:
            cats = {age_by_team[tid] for tid in team_ids if tid in age_by_team}
            if not (cats & {"VSE", "MSE"}):
                highest = max(
                    (_age_category_index(age_by_team[tid]) for tid in team_ids),
                    default=0,
                )
                if highest < game_order:
                    result[p.id] = (False, "Player's team is younger than game team")
                    continue
            if p.referee_certification == Player.RefereeCertification.NONE:
                result[p.id] = (False, "Missing required referee certification")
                continue
        result[p.id] = (True, None)

    return result


# ---------------------------------------------------------------------------
# Internal disqualification checks
# ---------------------------------------------------------------------------


def _already_assigned_to_game(player: Player, game: Game) -> bool:
    """Player is already on a task for this game."""
    return TaskAssignment.objects.filter(
        player=player,
        task__game=game,
    ).exists()


def _already_assigned_at_same_time(player: Player, game: Game) -> bool:
    """Player is already assigned to a task at the same date and time.

    Checks if the player has any task assignment for a game that plays at
    the exact same date/time (different game, same slot).
    """
    return (
        TaskAssignment.objects.filter(
            player=player,
            task__game__date=game.date,
            task__game__time=game.time,
        )
        .exclude(
            task__game=game,
        )
        .exists()
    )


def _team_has_home_game_at_same_time(player: Player, game: Game) -> bool:
    """Any team the player is responsible for has a home game at the same time.

    This only disqualifies the player if their team (or a coached team) plays
    another game at the same time (e.g., on a different court). If the player's
    team IS the home team for this game, they are already at the gym and eligible.
    """
    return (
        Game.objects.filter(
            own_team__in=player.all_teams,
            game_type=Game.GameType.HOME,
            date=game.date,
            time=game.time,
        )
        .exclude(pk=game.pk)
        .exists()
    )


def _team_has_away_game_on_same_day(player: Player, game: Game) -> bool:
    """Any team the player is responsible for has an away game on the same day.

    If the player's team (or a coached team) has an away game on the same day
    as this game, they can't be available for this task.

    ``own_team`` is always the club team the game is for, so away games are
    found by filtering on ``own_team``.
    """
    return Game.objects.filter(
        own_team__in=player.all_teams,
        game_type=Game.GameType.AWAY,
        date=game.date,
    ).exists()


def _player_team_involved_in_game(player: Player, game: Game, task_type: str) -> bool:
    """Any team the player is responsible for is involved in this game.

    Players should not be assigned to any task on a game where their own
    team or a coached team is playing.

    Exception: when the task is SCORER or TIMER and the team has
    `parent_responsible=True`, the player is eligible because parents are
    expected to fill those roles for their kid's team.
    """
    # ``own_team`` is always the club team the game is for, so the player's
    # team is involved only when it is the own_team.
    if game.own_team not in player.all_teams:
        return False

    if task_type in (TaskType.SCORER, TaskType.TIMER):
        # Exception: parents are expected to fill scorer/timer roles for their
        # kid's team when parent_responsible is set.
        if game.own_team.parent_responsible:
            return False

    return True


def _player_team_is_lower_age_than_game_team(player: Player, game: Game) -> bool:
    """The player's highest team is a lower age category than the game's home team.

    Checks the highest age category among all teams the player is responsible for
    (own team + coached teams).

    Adult teams (VSE, MSE) are always eligible to referee any game regardless of
    age category.
    """
    player_categories = {t.age_category for t in player.all_teams}
    # Adult teams can referee anything
    if player_categories & {"VSE", "MSE"}:
        return False

    highest_player_order = max(
        _age_category_index(t.age_category) for t in player.all_teams
    )
    game_order = _age_category_index(game.own_team.age_category)
    return highest_player_order < game_order


def _player_lacks_required_referee_certification(player: Player, game: Game) -> bool:
    """Player lacks the required referee certification for the game level.

    Rules:
    - Must have at least an F-diploma to referee
    - SENIOR certification qualifies for any game
    """
    return player.referee_certification == Player.RefereeCertification.NONE


def _age_category_index(category: str) -> int:
    """Return the index of an age category in the ordering."""
    try:
        return AGE_CATEGORY_ORDER.index(category)
    except ValueError:
        return 0


def _player_on_parent_responsible_team(player: Player) -> bool:
    """Check if any team the player belongs to has parent_responsible enabled."""
    return any(t.parent_responsible for t in player.all_teams)


def find_conflicting_assignments(
    season: Season | None = None,
) -> list[dict[str, Any]]:
    """Find existing task assignments that are no longer valid.

    When new games are added (e.g., away games), previously valid assignments
    may become invalid. This function scans all assignments and returns those
    where the player is now ineligible.

    Args:
        season: Optional season to scope the search. If None, checks all seasons.

    Returns:
        List of dicts with keys: assignment, player, task, game, reason.
    """
    qs = TaskAssignment.objects.select_related("player", "task", "task__game")
    if season is not None:
        qs = qs.filter(task__game__season=season)

    conflicts: list[dict[str, Any]] = []
    for assignment in qs:
        player = assignment.player
        task = assignment.task
        # Check all disqualification rules except "already assigned" which
        # is expected for a valid assignment.
        reasons = _get_conflict_reasons(player, task, assignment)
        for reason in reasons:
            conflicts.append(
                {
                    "assignment": assignment,
                    "player": player,
                    "task": task,
                    "game": task.game,
                    "reason": reason,
                }
            )
            break  # Report the first conflict reason
    return conflicts


def _get_conflict_reasons(
    player: Player,
    task: Task,
    assignment: TaskAssignment,
) -> list[str]:
    """Return all conflict reasons for an assignment (excluding self-assignment).

    This is like ``get_ineligibility_reason`` but checks *all* rules and
    skips the "already assigned" checks that always fire for existing assignments.
    """
    reasons: list[str] = []
    if player.is_exempt:
        reasons.append("Exempt from task assignments")
    if _team_has_home_game_at_same_time(player, task.game):
        reasons.append("Team has a home game at the same time")
    if _team_has_away_game_on_same_day(player, task.game):
        reasons.append("Team has an away game on the same day")
    if _player_team_involved_in_game(player, task.game, task.task_type):
        reasons.append("Cannot be assigned to own team's game")
    if task.task_type == TaskType.REFEREE:
        if _player_team_is_lower_age_than_game_team(player, task.game):
            reasons.append("Player's team is younger than game team")
        if _player_lacks_required_referee_certification(player, task.game):
            reasons.append("Missing required referee certification")
    # Check same-time conflicts with OTHER assignments (not self)
    other_at_time = TaskAssignment.objects.filter(
        player=player,
        task__game__date=task.game.date,
        task__game__time=task.game.time,
    ).exclude(pk=assignment.pk)
    if other_at_time.exists():
        reasons.append("Already assigned to another task at this time")
    return reasons
