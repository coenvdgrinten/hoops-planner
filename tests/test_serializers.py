"""Tests for serializers."""

import pytest
from rest_framework import serializers

from hoops_planner.core.models import (
    Player,
    TaskAssignment,
)
from hoops_planner.core.serializers import (
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
