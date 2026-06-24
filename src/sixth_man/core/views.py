"""API views for the Hoops Planner."""

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from sixth_man.core import suggestions as suggestion_logic
from sixth_man.core.eligibility import get_eligible_players_with_indicator
from sixth_man.core.models import (
    Game,
    Player,
    Season,
    Task,
    TaskAssignment,
    Team,
)
from sixth_man.core.serializers import (
    GameSerializer,
    PlayerSerializer,
    SeasonSerializer,
    TaskAssignmentSerializer,
    TaskSerializer,
    TeamSerializer,
)


class SeasonViewSet(viewsets.ModelViewSet):
    queryset = Season.objects.all()
    serializer_class = SeasonSerializer
    permission_classes = [permissions.AllowAny]


class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    permission_classes = [permissions.AllowAny]


class PlayerViewSet(viewsets.ModelViewSet):
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=["get"])
    def eligible(self, request):
        """Get eligible players for a task, with eligibility indicator."""
        task_id = request.query_params.get("task")
        if task_id is None:
            return Response(
                {"detail": "Provide task query parameter."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            task = Task.objects.get(pk=task_id)
        except Task.DoesNotExist:
            return Response(
                {"detail": "Task not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        results = get_eligible_players_with_indicator(task)
        data = [
            {
                "id": player.id,
                "first_name": player.first_name,
                "last_name": player.last_name,
                "full_name": player.full_name,
                "is_coach": player.is_coach,
                "team": player.team.name,
                "eligible": eligible,
            }
            for player, eligible in results
        ]
        return Response(data)


class GameViewSet(viewsets.ModelViewSet):
    queryset = Game.objects.all()
    serializer_class = GameSerializer
    permission_classes = [permissions.AllowAny]


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=True, methods=["get"])
    def suggestions(self, request, pk=None):
        """Get candidate suggestions for a task slot."""
        task = self.get_object()
        limit = int(request.query_params.get("limit", 5))
        candidates = suggestion_logic.suggest_candidates(task, limit=limit)
        serializer = PlayerSerializer(candidates, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def candidate_details(self, request, pk=None):
        """Get detailed candidate info with task count and at_gym flag."""
        task = self.get_object()
        limit = int(request.query_params.get("limit", 5))
        details = suggestion_logic.get_candidate_details(task, limit=limit)
        data = [
            {
                "player": PlayerSerializer(player).data,
                "task_count": task_count,
                "at_gym": at_gym,
            }
            for player, task_count, at_gym in details
        ]
        return Response(data)


class TaskAssignmentViewSet(viewsets.ModelViewSet):
    queryset = TaskAssignment.objects.all()
    serializer_class = TaskAssignmentSerializer
    permission_classes = [permissions.AllowAny]
