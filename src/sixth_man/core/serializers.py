"""Serializers for the Hoops Planner API."""

from rest_framework import serializers

from sixth_man.core.models import (
    Game,
    Player,
    Season,
    Task,
    TaskAssignment,
    Team,
)


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = [
            "id",
            "name",
            "age_category",
            "requires_24_second_operator",
        ]


class PlayerSerializer(serializers.ModelSerializer):
    team = TeamSerializer(read_only=True)
    team_id = serializers.PrimaryKeyRelatedField(
        queryset=Team.objects.all(),
        source="team",
        write_only=True,
    )

    class Meta:
        model = Player
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "team",
            "team_id",
            "is_coach",
            "referee_certification",
        ]
        read_only_fields = ["full_name"]


class SeasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Season
        fields = ["id", "name"]


class GameSerializer(serializers.ModelSerializer):
    home_team = TeamSerializer(read_only=True)
    home_team_id = serializers.PrimaryKeyRelatedField(
        queryset=Team.objects.all(),
        source="home_team",
        write_only=True,
    )

    class Meta:
        model = Game
        fields = [
            "id",
            "season",
            "home_team",
            "home_team_id",
            "away_team",
            "game_type",
            "date",
            "time",
            "court",
            "required_referees",
        ]


class TaskSerializer(serializers.ModelSerializer):
    game = GameSerializer(read_only=True)
    game_id = serializers.PrimaryKeyRelatedField(
        queryset=Game.objects.all(),
        source="game",
        write_only=True,
    )

    class Meta:
        model = Task
        fields = [
            "id",
            "game",
            "game_id",
            "task_type",
            "slot_number",
        ]


class TaskAssignmentSerializer(serializers.ModelSerializer):
    task = TaskSerializer(read_only=True)
    task_id = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(),
        source="task",
        write_only=True,
    )
    player = PlayerSerializer(read_only=True)
    player_id = serializers.PrimaryKeyRelatedField(
        queryset=Player.objects.all(),
        source="player",
        write_only=True,
    )

    class Meta:
        model = TaskAssignment
        fields = [
            "id",
            "task",
            "task_id",
            "player",
            "player_id",
            "assigned_at",
        ]


class TaskWithAssignmentsSerializer(serializers.ModelSerializer):
    """Task serializer with nested assignments for bulk endpoints."""
    assignments = TaskAssignmentSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = Task
        fields = [
            "id",
            "game",
            "task_type",
            "slot_number",
            "assignments",
        ]
        read_only_fields = ["assigned_at"]
