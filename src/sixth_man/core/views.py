"""API views for Hoops Planner."""

from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from sixth_man.core import statistics as stats_logic
from sixth_man.core import suggestions as suggestion_logic
from sixth_man.core.csv_export import export_schedule_csv
from sixth_man.core.eligibility import get_eligible_players_with_indicator
from sixth_man.core.importers import import_members, import_schedule
from sixth_man.core.models import (
    AgeCategorySettings,
    Game,
    Player,
    Season,
    Task,
    TaskAssignment,
    Team,
)
from sixth_man.core.pdf_export import export_schedule_pdf
from sixth_man.core.serializers import (
    AgeCategorySettingsSerializer,
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

    @action(detail=False, methods=["post"])
    def import_schedule(self, request):
        """Import a schedule CSV for this season.

        Accepts either a file upload ('file' field) or raw text ('csv_text' field).
        Optional: 'replace' (boolean, default False) — if True, deletes existing
        games before importing; if False, matches and updates existing games.
        """
        csv_file = request.FILES.get("file")
        csv_text = request.data.get("csv_text", "")
        season_name = request.data.get("season_name", "2025-2026")
        replace = request.data.get("replace", False)

        if csv_file:
            csv_text = csv_file.read().decode("utf-8-sig")

        if not csv_text:
            return Response(
                {
                    "detail": (
                        "Provide a 'file' field or 'csv_text' field with the CSV.",
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = import_schedule(csv_text, season_name, replace=bool(replace))
        return Response(result, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        """Get aggregate statistics for a season."""
        season = self.get_object()
        half = request.query_params.get("half")
        data = stats_logic.get_season_stats(season, half=half)
        return Response(data)

    @action(detail=True, methods=["get"])
    def leaderboard(self, request, pk=None):
        """Get leaderboard of players by effective task count."""
        season = self.get_object()
        top = int(request.query_params.get("top", 10))
        half = request.query_params.get("half")
        data = stats_logic.get_leaderboard(season, top=top, half=half)
        return Response(data)

    @action(detail=True, methods=["get"])
    def export_pdf(self, request, pk=None):
        """Export the task schedule as a PDF."""
        season = self.get_object()
        pdf_bytes = export_schedule_pdf(season)
        return HttpResponse(
            pdf_bytes,
            content_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="schedule_{season.name}.pdf"'
                ),
            },
        )

    @action(detail=True, methods=["get"])
    def export_csv(self, request, pk=None):
        """Export the task schedule (assignments) as a CSV."""
        season = self.get_object()
        csv_text = export_schedule_csv(season)
        return HttpResponse(
            csv_text,
            content_type="text/csv",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="schedule_{season.name}.csv"'
                ),
            },
        )


class TeamViewSet(viewsets.ModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer


class PlayerViewSet(viewsets.ModelViewSet):
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer

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
                        "Provide a 'file' field or 'csv_text' field with the CSV.",
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
        half = request.query_params.get("half")
        season = None
        if season_name:
            try:
                season = Season.objects.get(name=season_name)
            except Season.DoesNotExist:
                return Response(
                    {"detail": "Season not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        data = stats_logic.get_player_stats(player, season, half)
        return Response(data)

    @action(detail=True, methods=["get"])
    def upcoming(self, request, pk=None):
        """Get upcoming assignments for a player."""
        player = self.get_object()
        limit = int(request.query_params.get("limit", 20))
        data = stats_logic.get_upcoming_assignments(player, limit=limit)
        return Response(data)


class GameViewSet(viewsets.ModelViewSet):
    serializer_class = GameSerializer

    def get_queryset(self):
        qs = Game.objects.all()
        season = self.request.query_params.get("season")
        if season:
            qs = qs.filter(season_id=season)
        return qs

    def perform_create(self, serializer):
        game = serializer.save()
        # Auto-create task slots for new games
        from sixth_man.core.importers import _ensure_task_slots

        _ensure_task_slots(game)

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
                "at_gym": position,
                "suggestion_reason": reason,
            }
            for player, task_count, position, reason in details
        ]
        return Response(data)

    @action(detail=True, methods=["get"])
    def team_eligibility(self, request, pk=None):
        """Get all teams with their members, eligibility, and task counts."""
        task = self.get_object()
        results = suggestion_logic.get_team_eligibility(task)
        data = []
        for team_result in results:
            data.append(
                {
                    "team": TeamSerializer(team_result["team"]).data,
                    "players": [
                        {
                            "player": PlayerSerializer(p["player"]).data,
                            "eligible": p["eligible"],
                            "ineligible_reason": p.get("ineligible_reason"),
                            "task_count": p["task_count"],
                            "at_gym": p["at_gym"],
                        }
                        for p in team_result["players"]
                    ],
                    "eligible_count": team_result["eligible_count"],
                    "at_gym_day": team_result["at_gym_day"],
                }
            )
        return Response(data)


class TaskAssignmentViewSet(viewsets.ModelViewSet):
    queryset = TaskAssignment.objects.all()
    serializer_class = TaskAssignmentSerializer


class SettingsViewSet(viewsets.ViewSet):
    """Read/update per-age-category staffing settings."""

    def list(self, request):
        """Return settings for every age category (creating defaults as needed)."""
        settings = [
            AgeCategorySettings.for_category(category)
            for category in Team.AgeCategory.values
        ]
        serializer = AgeCategorySettingsSerializer(settings, many=True)
        return Response(serializer.data)

    def update(self, request, pk=None):
        """Update the settings for a single age category (pk is the category)."""
        if pk not in Team.AgeCategory.values:
            return Response(
                {"detail": "Unknown age category."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        obj = AgeCategorySettings.for_category(pk)
        serializer = AgeCategorySettingsSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AvailabilityViewSet(viewsets.ViewSet):
    """Show, per day, which members are unavailable due to away games.

    An away game for a team makes every member of that team (players and
    coaches) and anyone who coaches that team unavailable for tasks that day.
    This view surfaces that information so planners can see *why* a member
    cannot be assigned.
    """

    def list(self, request):
        season_id = request.query_params.get("season")
        if not season_id:
            return Response(
                {"detail": "Provide a 'season' query parameter."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        away_games = (
            Game.objects.filter(season_id=season_id, game_type=Game.GameType.AWAY)
            .select_related("home_team")
            .order_by("date", "time")
        )

        # Group away games by date
        by_date: dict[str, list[dict[str, object]]] = {}
        for game in away_games:
            team = game.home_team
            # Members made unavailable: players on the team + anyone coaching it
            players = list(
                Player.objects.filter(team=team).values(
                    "id", "first_name", "last_name", "is_coach"
                )
            )
            coaches_of_team = list(
                Player.objects.filter(coached_teams=team).values(
                    "id", "first_name", "last_name", "is_coach"
                )
            )
            # Merge, de-duplicating by player id
            seen = set()
            members = []
            for p in players + coaches_of_team:
                if p["id"] in seen:
                    continue
                seen.add(p["id"])
                members.append(
                    {
                        "id": p["id"],
                        "name": f"{p['first_name']} {p['last_name']}",
                        "is_coach": p["is_coach"],
                    }
                )

            entry = {
                "game_id": game.id,
                "team": TeamSerializer(team).data,
                "opponent": game.away_team,
                "time": game.time.strftime("%H:%M") if game.time else "",
                "member_count": len(members),
                "members": members,
            }
            by_date.setdefault(str(game.date), []).append(entry)

        data = [
            {"date": date, "away_games": games}
            for date, games in sorted(by_date.items())
        ]
        return Response(data)
