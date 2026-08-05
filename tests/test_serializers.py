"""Tests for serializers."""

import datetime as dt

import pytest
from rest_framework import serializers

from hoops_planner.core.models import (
    Game,
    Player,
    TaskAssignment,
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


@pytest.mark.django_db
class TestGameSerializer:
    def test_serializes_location(self, season, team_x14):
        game = Game.objects.create(
            season=season,
            home_team=team_x14,
            away_team="Achilles '71",
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
            home_team=team_x14,
            away_team="Achilles '71",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        serializer = GameSerializer(game)
        assert serializer.data["location"] == "Den Ekkerman"
