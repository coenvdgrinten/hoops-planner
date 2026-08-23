"""Tests for serializers."""

import datetime as dt

import pytest
from rest_framework import serializers

from hoops_planner.core.models import (
    Game,
    Player,
    Task,
    TaskAssignment,
    TaskType,
    Team,
)
from hoops_planner.core.serializers import (
    GameSerializer,
    TaskAssignmentSerializer,
)


@pytest.mark.django_db
class TestTaskAssignmentSerializer:
    def test_create_assignment_success(self, task, player):
        data = {"task_id": task.id, "player_id": player.id}
        serializer = TaskAssignmentSerializer(data=data)
        assert serializer.is_valid()
        assignment = serializer.save()
        assert assignment.task == task
        assert assignment.player == player

    def test_create_duplicate_assignment_raises_error(self, task, player, season):
        # Create first assignment
        TaskAssignment.objects.create(task=task, player=player)

        # Try to create second assignment on same task
        player2 = Player.objects.create(
            first_name="Other",
            last_name="Player",
            team=player.team,
        )
        data = {"task_id": task.id, "player_id": player2.id}
        serializer = TaskAssignmentSerializer(data=data)
        assert serializer.is_valid()
        with pytest.raises(serializers.ValidationError):
            serializer.save()

    def test_serializes_nested_data(self, task, player):
        assignment = TaskAssignment.objects.create(task=task, player=player)
        serializer = TaskAssignmentSerializer(assignment)
        data = serializer.data
        assert data["id"] == assignment.id
        assert data["player"]["id"] == player.id
        assert data["player"]["full_name"] == player.full_name
        assert data["task"]["id"] == task.id

    def test_is_parent_false_for_coach_of_other_parent_team(self, season):
        """A member of a non-parent team who coaches a parent team is NOT a
        parent for the non-parent team's scorer slot."""
        kid_team = Team.objects.create(
            name="Vido X12-2",
            age_category=Team.AgeCategory.X12,
            parent_responsible=True,
        )
        adult_team = Team.objects.create(
            name="Vido VSE1",
            age_category=Team.AgeCategory.VSE,
        )
        coach = Player.objects.create(
            first_name="Tessa", last_name="Kramer", team=adult_team,
        )
        coach.coached_teams.add(kid_team)

        game = Game.objects.create(
            season=season,
            own_team=adult_team,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(game=game, task_type=TaskType.SCORER, slot_number=1)
        assignment = TaskAssignment.objects.create(task=task, player=coach)

        data = TaskAssignmentSerializer(assignment).data
        assert data["is_parent"] is False

    def test_is_parent_true_for_own_parent_team(self, season):
        """A member of a parent_responsible team IS a parent for that team's
        scorer slot."""
        kid_team = Team.objects.create(
            name="Vido X12-2",
            age_category=Team.AgeCategory.X12,
            parent_responsible=True,
        )
        parent = Player.objects.create(
            first_name="Naima", last_name="Boerebach", team=kid_team,
        )
        game = Game.objects.create(
            season=season,
            own_team=kid_team,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(game=game, task_type=TaskType.TIMER, slot_number=1)
        assignment = TaskAssignment.objects.create(task=task, player=parent)

        data = TaskAssignmentSerializer(assignment).data
        assert data["is_parent"] is True


@pytest.mark.django_db
class TestGameSerializer:
    def test_serializes_location(self, season, team_x14):
        game = Game.objects.create(
            season=season,
            own_team=team_x14,
            opponent="Achilles '71",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
            location="De Kempencampus",
        )
        serializer = GameSerializer(game)
        assert serializer.data["location"] == "De Kempencampus"

    def test_defaults_location_to_den_ekkerman(self, season, team_x14):
        game = Game.objects.create(
            season=season,
            own_team=team_x14,
            opponent="Achilles '71",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        serializer = GameSerializer(game)
        assert serializer.data["location"] == "Den Ekkerman"
