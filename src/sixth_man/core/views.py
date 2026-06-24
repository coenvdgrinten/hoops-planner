"""API views for the Hoops Planner."""

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from sixth_man.core import statistics as stats_logic
from sixth_man.core import suggestions as suggestion_logic
from sixth_man.core.eligibility import get_eligible_players_with_indicator
from sixth_man.core.importers import import_members, import_schedule
from sixth_man.core.models import (
    Game,
    Player,
    Season,
    Task,
    TaskAssignment,
    Team,
)
from sixth_man.core.pdf_export import export_schedule_pdf
from sixth_man.core.serializers import (
    GameSerializer,
    PlayerSerializer,
    SeasonSerializer,
    TaskAssignmentSerializer,
    TaskSerializer,
    TaskWithAssignmentsSerializer,
    TeamSerializer,
)


class SeasonViewSet(viewsets.ModelViewSet):
    queryset = Season.objects.all()
    serializer_class = SeasonSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=["post"])
    def import_schedule(self, request):
        """Import a schedule CSV for this season.

        Accepts either a file upload ('file' field) or raw text ('csv_text' field).
        """
        csv_file = request.FILES.get("file")
        csv_text = request.data.get("csv_text", "")
        season_name = request.data.get("season_name", "2025-2026")

        if csv_file:
            csv_text = csv_file.read().decode("utf-8-sig")

        if not csv_text:
            return Response(
                {
                    "detail": (
                        "Provide a 'file' field or 'csv_text' " "field with the CSV.",
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = import_schedule(csv_text, season_name)
        return Response(result, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        """Get aggregate statistics for a season."""
        season = self.get_object()
        data = stats_logic.get_season_stats(season)
        return Response(data)

    @action(detail=True, methods=["get"])
    def leaderboard(self, request, pk=None):
        """Get leaderboard of players by effective task count."""
        season = self.get_object()
        top = int(request.query_params.get("top", 10))
        data = stats_logic.get_leaderboard(season, top=top)
        return Response(data)

    @action(detail=True, methods=["get"])
    def export_pdf(self, request, pk=None):
        """Export the task schedule as a PDF."""
        season = self.get_object()
        pdf_bytes = export_schedule_pdf(season)
        return Response(
            pdf_bytes,
            content_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="schedule_{season.name}.pdf"'
                ),
            },
        )


class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    permission_classes = [permissions.AllowAny]


class PlayerViewSet(viewsets.ModelViewSet):
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=["post"])
    def import_members(self, request):
        """Import a members CSV (players and teams).

        Accepts either a file upload ('file' field) or raw text ('csv_text' field).
        """
        csv_file = request.FILES.get("file")
        csv_text = request.data.get("csv_text", "")
        upsert = request.data.get("upsert", True)

        if csv_file:
            csv_text = csv_file.read().decode("utf-8-sig")

        if not csv_text:
            return Response(
                {
                    "detail": (
                        "Provide a 'file' field or 'csv_text' " "field with the CSV.",
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = import_members(csv_text, upsert=upsert)
        return Response(result, status=status.HTTP_201_CREATED)

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

    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        """Get statistics for a specific player."""
        player = self.get_object()
        season_name = request.query_params.get("season")
        season = None
        if season_name:
            try:
                season = Season.objects.get(name=season_name)
            except Season.DoesNotExist:
                return Response(
                    {"detail": "Season not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        data = stats_logic.get_player_stats(player, season)
        return Response(data)

    @action(detail=True, methods=["get"])
    def upcoming(self, request, pk=None):
        """Get upcoming assignments for a player."""
        player = self.get_object()
        limit = int(request.query_params.get("limit", 20))
        data = stats_logic.get_upcoming_assignments(player, limit=limit)
        return Response(data)


class GameViewSet(viewsets.ModelViewSet):
    queryset = Game.objects.all()
    serializer_class = GameSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=True, methods=["get"])
    def tasks_with_assignments(self, request, pk=None):
        """Get all tasks for this game with nested assignments."""
        game = self.get_object()
        tasks = Task.objects.filter(game=game).order_by("task_type", "slot_number")
        serializer = TaskWithAssignmentsSerializer(tasks, many=True)
        return Response(serializer.data)


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
