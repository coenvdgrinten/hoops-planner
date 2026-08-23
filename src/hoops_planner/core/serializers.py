"""Serializers for the Hoops Planner API."""

from django.core.exceptions import ValidationError
from rest_framework import serializers

from hoops_planner.core.eligibility import get_ineligibility_reason
from hoops_planner.core.models import (
    Game,
    Player,
    Season,
    Task,
    TaskAssignment,
    Team,
)


class TeamSerializer(serializers.ModelSerializer):
    total_tasks = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = [
            "id",
            "name",
            "age_category",
            "required_referees",
            "optional_referees",
            "require_scorer",
            "require_timer",
            "requires_24_second_operator",
            "parent_responsible",
            "total_tasks",
        ]

    def get_total_tasks(self, obj) -> int:
        return TaskAssignment.objects.filter(player__team=obj).count()


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
            "is_exempt",
        ]
        read_only_fields = ["full_name"]


class SeasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Season
        fields = ["id", "name"]


class GameSerializer(serializers.ModelSerializer):
    own_team = TeamSerializer(read_only=True)
    own_team_id = serializers.PrimaryKeyRelatedField(
        queryset=Team.objects.all(),
        source="own_team",
        write_only=True,
    )

    class Meta:
        model = Game
        fields = [
            "id",
            "season",
            "own_team",
            "own_team_id",
            "opponent",
            "game_type",
            "date",
            "time",
            "court",
            "location",
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
            "optional",
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
    is_parent = serializers.SerializerMethodField()
    effective_value = serializers.SerializerMethodField()
    has_other_task_same_day = serializers.SerializerMethodField()

    class Meta:
        model = TaskAssignment
        fields = [
            "id",
            "task",
            "task_id",
            "player",
            "player_id",
            "assigned_at",
            "is_parent",
            "effective_value",
            "has_other_task_same_day",
        ]

    def get_is_parent(self, obj: TaskAssignment) -> bool:
        """True when the player is acting as a parent for this task.

        Only applies when the *task's own team* is a ``parent_responsible``
        team and the player is a member or coach of that specific team. A
        player who merely coaches some other parent-responsible team (e.g. a
        VSE member coaching X12) must NOT be labelled a parent for an unrelated
        team's scorer/timer slot. Mirrors ``suggestions._is_parent_for_task``.
        """
        if obj.task.task_type not in ("SCORER", "TIMER"):
            return False
        own_team = obj.task.game.own_team
        if not own_team.parent_responsible:
            return False
        # Member or coach of the task's own team (uses prefetched data).
        if own_team.id == obj.player.team_id:
            return True
        return any(t.id == own_team.id for t in obj.player.coached_teams.all())

    def get_effective_value(self, obj: TaskAssignment) -> int:
        """How much this assignment counts toward the player's effective total.

        2 when none of the player's teams has a game on the task's date
        (away day), 1 otherwise — same rule as the season statistics.

        When the caller precomputes ``effective_multiplier_map`` and passes it
        via context (the bulk endpoints do), that value is used to avoid a
        per-assignment query. Otherwise fall back to the single-player helper.
        """
        multiplier_map = self.context.get("effective_multiplier_map")
        if multiplier_map is not None:
            return multiplier_map[obj.player_id][obj.task.game.date]
        from hoops_planner.core.statistics import effective_multiplier_for

        return effective_multiplier_for(obj.player, obj.task.game.date)

    def get_has_other_task_same_day(self, obj: TaskAssignment) -> bool:
        """True when the player holds another task on the game's date."""
        multi = self.context.get("same_day_multi_players")
        if multi is None:
            return (
                TaskAssignment.objects.filter(
                    player=obj.player,
                    task__game__date=obj.task.game.date,
                )
                .exclude(task=obj.task)
                .exists()
            )
        return obj.player_id in multi

    def create(self, validated_data):
        task = validated_data["task"]
        player = validated_data["player"]

        reason = get_ineligibility_reason(player, task)
        if reason:
            raise serializers.ValidationError(reason)

        assignment = TaskAssignment(task=task, player=player)
        try:
            assignment.full_clean(exclude=["assigned_at"])
        except ValidationError as exc:
            raise serializers.ValidationError(exc.messages[0]) from exc

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
