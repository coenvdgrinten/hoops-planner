"""Tests for model-level validation and methods."""

import datetime as dt

import pytest
from django.core.exceptions import ValidationError

from hoops_planner.core.models import (
    Game,
    Player,
    Season,
    Task,
    TaskAssignment,
    TaskType,
    Team,
)


@pytest.mark.django_db
class TestTaskAssignmentClean:
    def test_clean_valid_assignment(self, task, player):
        """A valid assignment should pass clean()."""
        assignment = TaskAssignment(task=task, player=player)
        assignment.clean()  # should not raise

    def test_clean_duplicate_task(self, task, player, season):
        """Assigning a second player to the same task should fail."""
        TaskAssignment.objects.create(task=task, player=player)
        player2 = Player.objects.create(
            first_name="Other",
            last_name="Player",
            team=player.team,
        )
        assignment = TaskAssignment(task=task, player=player2)
        with pytest.raises(ValidationError):
            assignment.clean()

    def test_clean_same_game(self, task, player, season):
        """Assigning a player to two tasks in the same game should fail."""
        TaskAssignment.objects.create(task=task, player=player)
        task2 = Task.objects.create(
            game=task.game,
            task_type=TaskType.TIMER,
            slot_number=1,
        )
        assignment = TaskAssignment(task=task2, player=player)
        with pytest.raises(ValidationError):
            assignment.clean()

    def test_clean_same_time(self, task, player, season):
        """Assigning a player to tasks at the same time should fail."""
        TaskAssignment.objects.create(task=task, player=player)
        # Create another game at the same time on a different court
        other_game = Game.objects.create(
            season=season,
            home_team=player.team,
            away_team="Other Opponent",
            game_type=Game.GameType.HOME,
            date=task.game.date,
            time=task.game.time,
            court=Game.Court.COURT_2,
        )
        task2 = Task.objects.create(
            game=other_game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        assignment = TaskAssignment(task=task2, player=player)
        with pytest.raises(ValidationError):
            assignment.clean()

    def test_clean_own_team_referee(self, season):
        """A player cannot referee their own team's game."""
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        player = Player.objects.create(
            first_name="John",
            last_name="Doe",
            team=team,
            referee_certification=Player.RefereeCertification.F,
        )
        game = Game.objects.create(
            season=season,
            home_team=team,
            away_team="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(
            game=game,
            task_type=TaskType.REFEREE,
            slot_number=1,
        )
        assignment = TaskAssignment(task=task, player=player)
        with pytest.raises(ValidationError):
            assignment.clean()

    def test_clean_own_team_scorer_without_parent_responsible(self, season):
        """A player cannot be scorer on own team unless parent_responsible."""
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
            parent_responsible=False,
        )
        player = Player.objects.create(
            first_name="John",
            last_name="Doe",
            team=team,
        )
        game = Game.objects.create(
            season=season,
            home_team=team,
            away_team="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        assignment = TaskAssignment(task=task, player=player)
        with pytest.raises(ValidationError):
            assignment.clean()

    def test_clean_own_team_scorer_with_parent_responsible(self, season):
        """A player CAN be scorer on own team when parent_responsible=True."""
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
            parent_responsible=True,
        )
        player = Player.objects.create(
            first_name="John",
            last_name="Doe",
            team=team,
        )
        game = Game.objects.create(
            season=season,
            home_team=team,
            away_team="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        assignment = TaskAssignment(task=task, player=player)
        assignment.clean()  # should not raise

    def test_clean_away_team_scorer_without_parent_responsible(self, season):
        """A player cannot be scorer on own away team unless parent_responsible."""
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
            parent_responsible=False,
        )
        player = Player.objects.create(
            first_name="John",
            last_name="Doe",
            team=team,
        )
        other_team = Team.objects.create(
            name="Vido X10-1",
            age_category=Team.AgeCategory.X10,
        )
        game = Game.objects.create(
            season=season,
            home_team=other_team,
            away_team="Vido X14-1",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        assignment = TaskAssignment(task=task, player=player)
        with pytest.raises(ValidationError):
            assignment.clean()

    def test_clean_away_team_scorer_with_parent_responsible(self, season):
        """A player CAN be scorer on own away team when parent_responsible."""
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
            parent_responsible=True,
        )
        player = Player.objects.create(
            first_name="John",
            last_name="Doe",
            team=team,
        )
        other_team = Team.objects.create(
            name="Vido X10-1",
            age_category=Team.AgeCategory.X10,
        )
        game = Game.objects.create(
            season=season,
            home_team=other_team,
            away_team="Vido X14-1",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        assignment = TaskAssignment(task=task, player=player)
        assignment.clean()  # should not raise


@pytest.mark.django_db
class TestModelStringMethods:
    def test_team_str(self, team_x14):
        assert str(team_x14) == "Vido X14-1"

    def test_player_str(self, player):
        assert str(player) == "John Doe"

    def test_player_full_name(self, player):
        assert player.full_name == "John Doe"

    def test_season_str(self, season):
        assert str(season) == "2025-2026"

    def test_game_str(self, season, team_x14):
        game = Game.objects.create(
            season=season,
            home_team=team_x14,
            away_team="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        assert str(game) == "Vido X14-1 vs Opponent (2025-10-01)"

    def test_task_str(self, task):
        assert "Scorer" in str(task)

    def test_task_assignment_str(self, task, player):
        assignment = TaskAssignment.objects.create(task=task, player=player)
        assert str(assignment) == f"John Doe -> {task}"

    def test_game_time_slot_key(self, season, team_x14):
        game = Game.objects.create(
            season=season,
            home_team=team_x14,
            away_team="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        assert game.time_slot_key == "2025-10-01T14:00:00"

    def test_player_all_teams_includes_coached(self, player, team_x10):
        """all_teams should include own team and coached teams."""
        player.coached_teams.add(team_x10)
        team_ids = {t.id for t in player.all_teams}
        assert player.team.id in team_ids
        assert team_x10.id in team_ids
