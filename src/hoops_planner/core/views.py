"""API views for Hoops Planner."""

from django.conf import settings
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response

from hoops_planner.core import statistics as stats_logic
from hoops_planner.core import suggestions as suggestion_logic
from hoops_planner.core.calendar_export import export_schedule_ics
from hoops_planner.core.csv_export import export_members_csv, export_schedule_csv
from hoops_planner.core.demo_seed import seed_demo_data
from hoops_planner.core.eligibility import (
    find_conflicting_assignments,
    get_eligible_players_with_indicator,
)
from hoops_planner.core.importers import import_members, import_schedule
from hoops_planner.core.models import (
    Game,
    Player,
    Season,
    Task,
    TaskAssignment,
    Team,
)
from hoops_planner.core.pdf_export import export_schedule_pdf
from hoops_planner.core.serializers import (
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
    def export_ics(self, request, pk=None):
        """Export the task schedule as an .ics calendar file."""
        season = self.get_object()
        ics_bytes = export_schedule_ics(season)
        return HttpResponse(
            ics_bytes,
            content_type="text/calendar; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="schedule_{season.name}.ics"'
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

    @action(detail=True, methods=["get"])
    def conflicts(self, request, pk=None):
        """Find task assignments that are no longer valid.

        Returns a list of assignments where the player has become ineligible
        due to newly added games (e.g., away games on the same day).
        """
        season = self.get_object()
        conflicts = find_conflicting_assignments(season=season)
        return Response(
            [
                {
                    "assignment_id": c["assignment"].id,
                    "player_id": c["player"].id,
                    "player_name": c["player"].full_name,
                    "task_type": c["task"].get_task_type_display(),
                    "game_id": c["game"].id,
                    "game_date": c["game"].date.isoformat(),
                    "game": str(c["game"]),
                    "reason": c["reason"],
                }
                for c in conflicts
            ]
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
    def export_members(self, request):
        """Export all team members as a CSV (same format as the members import)."""
        csv_text = export_members_csv()
        return HttpResponse(
            csv_text,
            content_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="members.csv"',
            },
        )

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
        from hoops_planner.core.importers import _ensure_task_slots

        _ensure_task_slots(game)

    @action(detail=True, methods=["get"])
    def tasks_with_assignments(self, request, pk=None):
        """Get all tasks for this game with nested assignments."""
        game = self.get_object()
        tasks = (
            Task.objects.filter(game=game)
            .select_related("game")
            .prefetch_related(
                "assignments__player",
                "assignments__player__team",
                "assignments__player__coached_teams",
            )
            .order_by("task_type", "slot_number")
        )
        # Precompute each assigned player's effective multiplier in a couple of
        # queries so the serializer doesn't fire one per assignment.
        players = list(
            {a.player for t in tasks for a in t.assignments.all()}
        )
        multiplier_map = stats_logic.effective_multiplier_map(
            players, {game.date}
        )
        serializer = TaskWithAssignmentsSerializer(
            tasks, many=True, context={"effective_multiplier_map": multiplier_map}
        )
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def clear_assignments(self, request, pk=None):
        """Remove all task assignments for this game."""
        game = self.get_object()
        count, _ = TaskAssignment.objects.filter(task__game=game).delete()
        return Response({"cleared": count})


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer

    def get_queryset(self):
        qs = Task.objects.all()
        game = self.request.query_params.get("game")
        if game:
            qs = qs.filter(game_id=game)
        return qs

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
                "task_count": player.assignments.count(),
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
                    "total_tasks": team_result["total_tasks"],
                }
            )
        return Response(data)


class TaskAssignmentViewSet(viewsets.ModelViewSet):
    queryset = TaskAssignment.objects.all()
    serializer_class = TaskAssignmentSerializer


class SettingsViewSet(viewsets.ViewSet):
    """Read/update per-team staffing settings."""

    def list(self, request):
        """Return settings for every team."""
        teams = Team.objects.all()
        serializer = TeamSerializer(teams, many=True)
        return Response(serializer.data)

    def update(self, request, pk=None):
        """Update the settings for a single team (pk is the team id)."""
        try:
            team = Team.objects.get(pk=pk)
        except Team.DoesNotExist:
            return Response(
                {"detail": "Unknown team."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = TeamSerializer(team, data=request.data, partial=True)
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
            .select_related("own_team")
            .order_by("date", "time")
        )

        # Group away games by date
        by_date: dict[str, list[dict[str, object]]] = {}
        for game in away_games:
            team = game.own_team
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
                "opponent": game.opponent,
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


@permission_classes([AllowAny])
def game_ics(request):
    """Export a single game as an .ics calendar event (public endpoint)."""
    game_id = request.GET.get("game_id")
    if not game_id:
        return HttpResponse(
            "game_id parameter is required",
            status=400,
            content_type="text/plain",
        )
    try:
        game = Game.objects.get(pk=game_id)
    except Game.DoesNotExist:
        return HttpResponse(
            "Game not found",
            status=404,
            content_type="text/plain",
        )
    ics_bytes = _generate_single_game_ics(game)
    return HttpResponse(
        ics_bytes,
        content_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": (f'attachment; filename="game_{game.id}.ics"'),
        },
    )


def _generate_single_game_ics(game: Game) -> bytes:
    """Generate a .ics file for a single game (public endpoint \u2014 no PII)."""
    from datetime import datetime, timedelta

    from hoops_planner.core.calendar_export import TASK_LABELS
    from hoops_planner.core.models import TaskAssignment

    dtstart = datetime.combine(game.date, game.time)
    dtend = dtstart + timedelta(hours=2)
    summary = f"{game.own_team} vs {game.opponent}"

    # Count assigned tasks by type only \u2014 never expose player names publicly
    assignments = TaskAssignment.objects.filter(task__game=game).select_related("task")
    if assignments:
        type_counts: dict[str, int] = {}
        for a in assignments:
            label = TASK_LABELS.get(a.task.task_type, a.task.task_type)
            type_counts[label] = type_counts.get(label, 0) + 1
        desc_parts = [
            f"{label}: {count} assigned" for label, count in type_counts.items()
        ]
        description = " | ".join(desc_parts)
    else:
        description = "No tasks assigned yet"

    ics_content = (
        "BEGIN:VCALENDAR\n"
        "VERSION:2.0\n"
        "PRODID:-//Hoops Planner//Game Event//EN\n"
        "BEGIN:VEVENT\n"
        f"DTSTART:{dtstart.strftime('%Y%m%dT%H%M%S')}\n"
        f"DTEND:{dtend.strftime('%Y%m%dT%H%M%S')}\n"
        f"SUMMARY:{summary}\n"
        f"DESCRIPTION:{description}\n"
        f"LOCATION:{game.location or 'Den Ekkerman'} - Court {game.court}\n"
        "STATUS:CONFIRMED\n"
        "END:VEVENT\n"
        "END:VCALENDAR\n"
    )

    return ics_content.encode("utf-8")


@api_view(["POST"])
@permission_classes([IsAdminUser])
def seed(request):
    """Seed demo data (admin only, and only when DEBUG is enabled).

    A development convenience so the Playwright e2e fixture — or a human — can
    populate the database over HTTP without needing shell access to the
    backend container. It is disabled entirely outside DEBUG.
    """
    if not settings.DEBUG:
        return Response(
            {"detail": "Seeding is only available in DEBUG mode."},
            status=status.HTTP_403_FORBIDDEN,
        )
    summary = seed_demo_data()
    return Response(summary, status=status.HTTP_201_CREATED)
