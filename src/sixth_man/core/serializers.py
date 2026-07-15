"""Serializers for the Sixth Man API."""

from rest_framework import serializers

from sixth_man.core.models import (
    AgeCategorySettings,
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
        ]


class PlayerSerializer(serializers.ModelSerializer):
    team = TeamSerializer(read_only=True)
    team_id = serializers.PrimaryKeyRelatedField(
        queryset=Team.objects.all(),
        source="team",
        write_only=True,
    )
    coached_teams = serializers.PrimaryKeyRelatedField(
        queryset=Team.objects.all(),
        many=True,
        required=False,
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
            "coached_teams",
            "referee_certification",
        ]
        read_only_fields = ["full_name"]


class SeasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Season
        fields = ["id", "name"]


class AgeCategorySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgeCategorySettings
        fields = [
            "age_category",
            "required_referees",
            "scorer",
            "timer",
            "requires_24_second_operator",
        ]
        read_only_fields = ["age_category"]


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
            "half",
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

    def create(self, validated_data):
        task = validated_data["task"]
        player = validated_data["player"]

        if task.assignments.exists():
            raise serializers.ValidationError(
                "This task already has an assignment. Remove it first."
            )

        # Player must not already be assigned to another task in the same game
        if TaskAssignment.objects.filter(
            player=player,
            task__game=task.game,
        ).exists():
            raise serializers.ValidationError(
                "This player is already assigned to another task in this game."
            )

        # Player must not be assigned to another task at the same date/time
        if (
            TaskAssignment.objects.filter(
                player=player,
                task__game__date=task.game.date,
                task__game__time=task.game.time,
            )
            .exclude(
                task__game=task.game,
            )
            .exists()
        ):
            raise serializers.ValidationError(
                "This player is already assigned to another task at this time."
            )

        # Players must not be assigned to their own team's games
        game = task.game
        if game.home_team == player.team:
            raise serializers.ValidationError(
                "A player cannot be assigned to their own team's game."
            )
        if game.away_team == player.team.name:
            raise serializers.ValidationError(
                "A player cannot be assigned to their own team's game."
            )

        return super().create(validated_data)


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
