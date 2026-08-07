"""Eligibility checks for task assignments."""

from hoops_planner.core.models import (
    Game,
    Player,
    Task,
    TaskAssignment,
    TaskType,
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
            home_team__in=player.all_teams,
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

    For AWAY games the player's team is stored in the away_team CharField,
    not the home_team FK.
    """
    team_names = [t.name for t in player.all_teams]
    return Game.objects.filter(
        away_team__in=team_names,
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
    if task_type in (TaskType.SCORER, TaskType.TIMER):
        # Check if the player's team is involved AND has parent_responsible
        involved_teams = [t for t in player.all_teams if t in (game.home_team,)]
        involved_teams += [t for t in player.all_teams if t.name == game.away_team]
        if involved_teams and all(t.parent_responsible for t in involved_teams):
            return False

    if game.home_team in player.all_teams:
        return True
    if game.away_team in [t.name for t in player.all_teams]:
        return True
    return False


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
    game_order = _age_category_index(game.home_team.age_category)
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
