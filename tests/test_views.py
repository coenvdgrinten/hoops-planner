"""Tests for API views."""

import datetime as dt

import pytest

from hoops_planner.core.models import (
    Game,
    Player,
    Season,
    Task,
    TaskAssignment,
    TaskType,
    Team,
)


@pytest.mark.django_db
class TestTeamViewSet:
    def test_create_team(self, api_client):
        response = api_client.post(
            "/api/teams/",
            {"name": "Vido X14-2", "age_category": Team.AgeCategory.X14},
            format="json",
        )
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Vido X14-2"
        assert body["age_category"] == Team.AgeCategory.X14
        assert Team.objects.filter(name="Vido X14-2").exists()

    def test_create_team_requires_name(self, api_client):
        response = api_client.post(
            "/api/teams/", {"age_category": Team.AgeCategory.X14}, format="json"
        )
        assert response.status_code == 400

    def test_update_team(self, api_client, team_x14):
        response = api_client.patch(
            f"/api/teams/{team_x14.id}/",
            {"name": "Vido X14-Renamed"},
            format="json",
        )
        assert response.status_code == 200
        team_x14.refresh_from_db()
        assert team_x14.name == "Vido X14-Renamed"

    def test_delete_team(self, api_client, team_x14):
        response = api_client.delete(f"/api/teams/{team_x14.id}/")
        assert response.status_code == 204
        assert not Team.objects.filter(id=team_x14.id).exists()


@pytest.mark.django_db
class TestPlayerViewSet:
    def test_create_player(self, api_client, team_x14):
        response = api_client.post(
            "/api/players/",
            {
                "first_name": "New",
                "last_name": "Player",
                "team_id": team_x14.id,
                "referee_certification": Player.RefereeCertification.T1,
            },
            format="json",
        )
        assert response.status_code == 201
        body = response.json()
        assert body["full_name"] == "New Player"
        assert Player.objects.filter(first_name="New", last_name="Player").exists()

    def test_create_player_requires_names(self, api_client, team_x14):
        response = api_client.post(
            "/api/players/", {"team_id": team_x14.id}, format="json"
        )
        assert response.status_code == 400

    def test_update_player(self, api_client, player):
        response = api_client.patch(
            f"/api/players/{player.id}/",
            {"referee_certification": Player.RefereeCertification.F},
            format="json",
        )
        assert response.status_code == 200
        player.refresh_from_db()
        assert player.referee_certification == Player.RefereeCertification.F

    def test_delete_player(self, api_client, player):
        response = api_client.delete(f"/api/players/{player.id}/")
        assert response.status_code == 204
        assert not Player.objects.filter(id=player.id).exists()


@pytest.mark.django_db
class TestSeasonViewSet:
    def test_create_season(self, api_client):
        response = api_client.post(
            "/api/seasons/", {"name": "2026-2027"}, format="json"
        )
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "2026-2027"
        assert Season.objects.filter(name="2026-2027").exists()

    def test_create_season_requires_name(self, api_client):
        response = api_client.post("/api/seasons/", {}, format="json")
        assert response.status_code == 400

    def test_create_season_duplicate_name_conflicts(self, api_client, season):
        response = api_client.post(
            "/api/seasons/", {"name": season.name}, format="json"
        )
        assert response.status_code == 400

    def test_export_csv(self, api_client, season, team_x14, player):
        from datetime import date, time

        from hoops_planner.core.models import Game, Task, TaskAssignment

        game = Game.objects.create(
            season=season,
            own_team=team_x14,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=date(2025, 10, 1),
            time=time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(game=game, task_type="SCORER", slot_number=1)
        TaskAssignment.objects.create(task=task, player=player)

        response = api_client.get(f"/api/seasons/{season.id}/export_csv/")
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"
        assert (
            response["Content-Disposition"]
            == f'attachment; filename="schedule_{season.name}.csv"'
        )
        body = response.content.decode()
        assert "date,time,court" in body
        assert "John Doe" in body
        assert "Vido X14-1" in body

    def test_export_pdf(self, api_client, season, team_x14, player):
        from datetime import date, time

        from hoops_planner.core.models import Game, Task, TaskAssignment

        game = Game.objects.create(
            season=season,
            own_team=team_x14,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=date(2025, 10, 1),
            time=time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(game=game, task_type="SCORER", slot_number=1)
        TaskAssignment.objects.create(task=task, player=player)

        response = api_client.get(f"/api/seasons/{season.id}/export_pdf/")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert (
            response["Content-Disposition"]
            == f'attachment; filename="schedule_{season.name}.pdf"'
        )
        assert response.content.startswith(b"%PDF")

    def test_export_ics(self, api_client, season, team_x14):
        from datetime import date, time

        from hoops_planner.core.models import Game, Task

        game = Game.objects.create(
            season=season,
            own_team=team_x14,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=date(2025, 10, 1),
            time=time(14, 0),
            court=Game.Court.COURT_1,
        )
        Task.objects.create(game=game, task_type="SCORER", slot_number=1)

        response = api_client.get(f"/api/seasons/{season.id}/export_ics/")
        assert response.status_code == 200
        assert response["Content-Type"] == "text/calendar; charset=utf-8"
        assert (
            response["Content-Disposition"]
            == f'attachment; filename="schedule_{season.name}.ics"'
        )
        body = response.content.decode("utf-8")
        assert "BEGIN:VCALENDAR" in body
        assert "BEGIN:VEVENT" in body
        assert "END:VCALENDAR" in body
        assert "Tafelen (Scorer) Vido X14-1 vs Opponent" in body

    def test_game_ics_public_access(self, season, team_x14, player):
        """The game_ics endpoint should be accessible without authentication."""
        from datetime import date, time

        from rest_framework.test import APIClient

        from hoops_planner.core.models import Game, Task, TaskAssignment

        game = Game.objects.create(
            season=season,
            own_team=team_x14,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=date(2025, 10, 1),
            time=time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(game=game, task_type="SCORER", slot_number=1)
        TaskAssignment.objects.create(task=task, player=player)

        # Use an unauthenticated client
        anon_client = APIClient()
        response = anon_client.get(f"/api/game_ics/?game_id={game.id}")
        assert response.status_code == 200
        assert response["Content-Type"] == "text/calendar; charset=utf-8"
        body = response.content.decode("utf-8")
        assert "BEGIN:VCALENDAR" in body
        assert "BEGIN:VEVENT" in body
        assert "END:VCALENDAR" in body
        # One event per task with the label in the summary
        assert "Tafelen (Scorer) Vido X14-1 vs Opponent" in body
        # Public endpoint must NOT expose player names (PII)
        assert "John Doe" not in body

    def test_game_ics_missing_game_id(self):
        """The game_ics endpoint should return 400 when game_id is missing."""
        from rest_framework.test import APIClient

        anon_client = APIClient()
        response = anon_client.get("/api/game_ics/")
        assert response.status_code == 400

    def test_game_ics_invalid_game_id(self):
        """The game_ics endpoint should return 404 for non-existent game."""
        from rest_framework.test import APIClient

        anon_client = APIClient()
        response = anon_client.get("/api/game_ics/?game_id=99999")
        assert response.status_code == 404

    def test_import_schedule_creates_season_and_games(self, api_client):
        csv_text = (
            "date,time,court,home_team,away_team\n"
            "2025-10-01,14:00,1,Team A,Team B\n"
            "2025-10-01,14:00,2,Team C,Team D"
        )
        response = api_client.post(
            "/api/seasons/import_schedule/",
            {"season_name": "Imported-2025", "csv_text": csv_text},
            format="json",
        )
        assert response.status_code == 201
        body = response.json()
        assert body["games_created"] == 2
        assert Season.objects.filter(name="Imported-2025").exists()
        assert Game.objects.filter(season__name="Imported-2025").count() == 2

    def test_import_schedule_requires_csv(self, api_client):
        response = api_client.post(
            "/api/seasons/import_schedule/",
            {"season_name": "NoCsv"},
            format="json",
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestPlayerEligibleViewAction:
    def test_missing_task_param(self, api_client):
        response = api_client.get("/api/players/eligible/")
        assert response.status_code == 400

    def test_invalid_task_id(self, api_client):
        response = api_client.get("/api/players/eligible/?task=99999")
        assert response.status_code == 404

    def test_returns_eligible_indicator(self, api_client, player, task):
        response = api_client.get(f"/api/players/eligible/?task={task.id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        names = [d["full_name"] for d in data]
        assert player.full_name in names
        # Each entry carries the eligibility indicator
        assert "eligible" in data[0]


@pytest.mark.django_db
class TestGameViewSet:
    def test_list_games_without_season_filter(self, api_client, season):
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        Game.objects.create(
            season=season,
            own_team=team,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        other_season = Season.objects.create(name="2024-2025")
        Game.objects.create(
            season=other_season,
            own_team=team,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_2,
        )

        response = api_client.get("/api/games/")
        assert response.status_code == 200
        assert response.json()["count"] == 2
        assert len(response.json()["results"]) == 2

    def test_list_games_with_season_filter(self, api_client, season):
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        Game.objects.create(
            season=season,
            own_team=team,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        other_season = Season.objects.create(name="2024-2025")
        Game.objects.create(
            season=other_season,
            own_team=team,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_2,
        )

        response = api_client.get(f"/api/games/?season={season.id}")
        assert response.status_code == 200
        assert response.json()["count"] == 1
        assert len(response.json()["results"]) == 1

    def test_tasks_with_assignments(self, api_client, player, season):
        game = Game.objects.create(
            season=season,
            own_team=player.team,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        TaskAssignment.objects.create(player=player, task=task)

        response = api_client.get(f"/api/games/{game.id}/tasks_with_assignments/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["task_type"] == "SCORER"
        assert len(data[0]["assignments"]) == 1
        # Own team has a game on this date → counts single
        assert data[0]["assignments"][0]["effective_value"] == 1

    def test_tasks_with_assignments_effective_value_away(
        self, api_client, player, season
    ):
        # Task on another team's game, on a date with no game for the
        # player's own team → counts double
        other_team = Team.objects.create(
            name="Vido X14-2",
            age_category=Team.AgeCategory.X14,
        )
        game = Game.objects.create(
            season=season,
            own_team=other_team,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        TaskAssignment.objects.create(player=player, task=task)

        response = api_client.get(f"/api/games/{game.id}/tasks_with_assignments/")
        assert response.status_code == 200
        data = response.json()
        assert data[0]["assignments"][0]["effective_value"] == 2


@pytest.mark.django_db
class TestTaskViewSet:
    def test_filters_by_game(self, api_client, task, season):
        # A task on another game must not appear in the filtered list
        other_team = Team.objects.create(
            name="Vido X14-3",
            age_category=Team.AgeCategory.X14,
        )
        other_game = Game.objects.create(
            season=season,
            own_team=other_team,
            opponent="Other Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 2),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        Task.objects.create(
            game=other_game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )

        response = api_client.get(f"/api/tasks/?game={task.game_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["id"] == task.id

    def test_no_filter_returns_all(self, api_client, task):
        response = api_client.get("/api/tasks/")
        assert response.status_code == 200
        data = response.json()
        assert any(t["id"] == task.id for t in data["results"])


@pytest.mark.django_db
class TestPlayerEligibleEndpoint:
    def test_missing_task_param(self, api_client, season):
        response = api_client.get("/api/players/eligible/")
        assert response.status_code == 400

    def test_invalid_task_id(self, api_client):
        response = api_client.get("/api/players/eligible/?task=99999")
        assert response.status_code == 404

    def test_returns_eligible_players(self, api_client, player, task):
        response = api_client.get(f"/api/players/eligible/?task={task.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        names = [d["full_name"] for d in data]
        assert player.full_name in names


@pytest.mark.django_db
class TestPlayerStatsEndpoint:
    def test_player_stats_no_season(self, api_client, player, season):
        game = Game.objects.create(
            season=season,
            own_team=player.team,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        TaskAssignment.objects.create(player=player, task=task)

        response = api_client.get(f"/api/players/{player.id}/stats/")
        assert response.status_code == 200
        data = response.json()
        assert data["total_tasks"] == 1

    def test_player_stats_with_season(self, api_client, player, season):
        game = Game.objects.create(
            season=season,
            own_team=player.team,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        TaskAssignment.objects.create(player=player, task=task)

        response = api_client.get(
            f"/api/players/{player.id}/stats/?season={season.name}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_tasks"] == 1

    def test_player_stats_invalid_season(self, api_client, player):
        response = api_client.get("/api/players/1/stats/?season=nonexistent")
        assert response.status_code == 404


@pytest.mark.django_db
class TestSeasonStatsEndpoint:
    def test_season_stats(self, api_client, season):
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        player = Player.objects.create(
            first_name="Player",
            last_name="One",
            team=team,
        )
        game = Game.objects.create(
            season=season,
            own_team=team,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        TaskAssignment.objects.create(player=player, task=task)

        response = api_client.get(f"/api/seasons/{season.id}/stats/")
        assert response.status_code == 200
        data = response.json()
        assert data["total_games"] == 1
        assert data["total_assignments"] == 1

    def test_stats_open_task_slots(self, api_client, season, team_x14):
        game = Game.objects.create(
            season=season,
            own_team=team_x14,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        # One assigned scorer, one unassigned referee.
        player = Player.objects.create(first_name="P1", last_name="L1", team=team_x14)
        scorer = Task.objects.create(
            game=game, task_type=TaskType.SCORER, slot_number=1
        )
        ref = Task.objects.create(game=game, task_type=TaskType.REFEREE, slot_number=1)
        TaskAssignment.objects.create(player=player, task=scorer)

        response = api_client.get(f"/api/seasons/{season.id}/stats/")
        assert response.status_code == 200
        data = response.json()
        assert data["open_task_slots"] == 1
        assert data["open_by_task_type"] == {TaskType.REFEREE: 1}

        TaskAssignment.objects.create(player=player, task=ref)
        response = api_client.get(f"/api/seasons/{season.id}/stats/")
        data = response.json()
        assert data["open_task_slots"] == 0
        assert data["open_by_task_type"] == {}


@pytest.mark.django_db
class TestSeasonLeaderboardEndpoint:
    def test_leaderboard(self, api_client, season):
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        player = Player.objects.create(
            first_name="Player",
            last_name="One",
            team=team,
        )
        game = Game.objects.create(
            season=season,
            own_team=team,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        TaskAssignment.objects.create(player=player, task=task)

        response = api_client.get(f"/api/seasons/{season.id}/leaderboard/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["player_name"] == player.full_name


@pytest.mark.django_db
class TestPlayerUpcomingEndpoint:
    def test_upcoming_assignments(self, api_client, player, season):
        game = Game.objects.create(
            season=season,
            own_team=player.team,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2027, 1, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        TaskAssignment.objects.create(player=player, task=task)

        response = api_client.get(f"/api/players/{player.id}/upcoming/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["game_date"] == "2027-01-01"


@pytest.mark.django_db
class TestImportEndpoints:
    def test_import_schedule_missing_csv(self, api_client):
        response = api_client.post(
            "/api/seasons/import_schedule/",
            {"season_name": "2025-2026"},
            format="json",
        )
        assert response.status_code == 400

    def test_import_members_missing_csv(self, api_client):
        response = api_client.post(
            "/api/players/import_members/",
            {},
            format="json",
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestExportMembersEndpoint:
    def test_export_members_csv(self, api_client, team_x14, player):
        response = api_client.get("/api/players/export_members/")
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"
        assert response["Content-Disposition"] == 'attachment; filename="members.csv"'
        body = response.content.decode()
        header = body.splitlines()[0]
        assert header.startswith("first_name,last_name,team,is_coach")
        assert "John,Doe,Vido X14-1,False,NONE" in body

    def test_export_round_trip_reimports(self, api_client, team_x14, player, referee):
        """The exported CSV must be re-importable without creating duplicates."""
        from hoops_planner.core.importers import import_members

        # Give the coach an extra coached team so the column is exercised.
        other = Team.objects.create(name="Vido X16-1", age_category="X16")
        referee.coached_teams.add(other)

        csv_text = api_client.get("/api/players/export_members/").content.decode()

        # Wipe everything, then re-import the exported text.
        Player.objects.all().delete()
        Team.objects.all().delete()
        result = import_members(csv_text)
        assert result["players_created"] == 2
        assert result["teams"] == 2
        # Coached teams survived the round trip.
        reimported = Player.objects.get(first_name="Jane")
        assert list(reimported.coached_teams.values_list("name", flat=True)) == [
            "Vido X16-1"
        ]

    def test_export_then_import_endpoint_round_trip(self, api_client):
        """Export via the API, wipe the DB, re-import via the API, compare.

        Exercises the exact flow a user would perform: download members.csv,
        paste it into the Import Members modal. Uses a realistic roster with
        coaches, coached teams, exemptions, and varied certifications.
        """
        t_x14 = Team.objects.create(name="Vido X14-1", age_category="X14")
        t_x10 = Team.objects.create(name="Vido X10-1", age_category="X10")
        t_vse = Team.objects.create(name="Vido VSE1", age_category="VSE")

        coach = Player.objects.create(
            first_name="Luc",
            last_name="Delaere",
            team=t_x14,
            is_coach=True,
            referee_certification="T2",
        )
        # Coach also coaches two other teams (multi-value coached_teams).
        coach.coached_teams.add(t_x10, t_vse)
        Player.objects.create(
            first_name="Jan",
            last_name="Janssens",
            team=t_x10,
            is_exempt=True,
        )
        Player.objects.create(
            first_name="Louis",
            last_name="Van Wijnendaele",
            team=t_vse,
            referee_certification="SENIOR",
        )
        Player.objects.create(
            first_name="Pieter",
            last_name="Van Damme",
            team=t_x14,
        )

        def snapshot():
            return {
                p.full_name: {
                    "team": p.team.name,
                    "is_coach": p.is_coach,
                    "cert": p.referee_certification,
                    "is_exempt": p.is_exempt,
                    "coached": sorted(p.coached_teams.values_list("name", flat=True)),
                }
                for p in Player.objects.select_related("team").all()
            }

        before = snapshot()

        # 1. Export through the real endpoint.
        csv_text = api_client.get("/api/players/export_members/").content.decode()

        # 2. Wipe everything, as if starting from an empty club.
        Player.objects.all().delete()
        Team.objects.all().delete()
        assert Player.objects.count() == 0

        # 3. Re-import the exported bytes through the real endpoint.
        resp = api_client.post(
            "/api/players/import_members/",
            {"csv_text": csv_text, "upsert": True},
            format="json",
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["players_created"] == 4
        assert body["players_updated"] == 0
        assert Team.objects.count() == 3

        after = snapshot()
        assert after == before


@pytest.mark.django_db
class TestSettingsEndpoint:
    def test_list_returns_all_teams(self, api_client):
        Team.objects.create(name="Vido X14-1", age_category="X14")
        Team.objects.create(name="Vido X10-1", age_category="X10")
        response = api_client.get("/api/settings/")
        assert response.status_code == 200
        data = response.json()
        team_names = {row["name"] for row in data}
        assert "Vido X14-1" in team_names
        assert "Vido X10-1" in team_names

    def test_update_changes_settings(self, api_client):
        team = Team.objects.create(name="Vido X14-1", age_category="X14")
        response = api_client.put(
            f"/api/settings/{team.id}/",
            {"required_referees": 3, "requires_24_second_operator": True},
            format="json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["required_referees"] == 3
        assert data["requires_24_second_operator"] is True

    def test_update_unknown_team(self, api_client):
        response = api_client.put(
            "/api/settings/99999/",
            {"required_referees": 1},
            format="json",
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestAvailabilityEndpoint:
    def test_requires_season_param(self, api_client):
        response = api_client.get("/api/availability/")
        assert response.status_code == 400

    def test_lists_away_games_with_unavailable_members(self, api_client, season):
        away_team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        Player.objects.create(
            first_name="Jane", last_name="Doe", team=away_team, is_coach=True
        )
        Player.objects.create(first_name="John", last_name="Smith", team=away_team)
        # A coach of another team who also coaches the away team
        other_team = Team.objects.create(
            name="Vido X10-1", age_category=Team.AgeCategory.X10
        )
        cross_coach = Player.objects.create(
            first_name="Coach", last_name="Karlos", team=other_team, is_coach=True
        )
        cross_coach.coached_teams.add(away_team)

        Game.objects.create(
            season=season,
            own_team=away_team,
            opponent="Opponent A",
            game_type=Game.GameType.AWAY,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        # A home game should NOT appear in availability
        Game.objects.create(
            season=season,
            own_team=away_team,
            opponent="Opponent B",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(16, 0),
            court=Game.Court.COURT_1,
        )

        response = api_client.get(f"/api/availability/?season={season.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        day = data[0]
        assert day["date"] == "2025-10-01"
        assert len(day["away_games"]) == 1
        game = day["away_games"][0]
        assert game["team"]["name"] == "Vido X14-1"
        assert game["opponent"] == "Opponent A"
        # Jane (player+coach), John (player), Coach Karlos (coaches away team)
        assert game["member_count"] == 3
        names = {m["name"] for m in game["members"]}
        assert "Jane Doe" in names
        assert "John Smith" in names
        assert "Coach Karlos" in names


@pytest.mark.django_db
class TestSeasonConflictsEndpoint:
    def test_no_conflicts(self, api_client, season, team_x14, player):
        """Empty season should return no conflicts."""
        response = api_client.get(f"/api/seasons/{season.id}/conflicts/")
        assert response.status_code == 200
        assert response.json() == []

    def test_conflict_detected(self, api_client, season):
        """Away game on same day should trigger a conflict."""
        team_a = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        team_b = Team.objects.create(
            name="Vido X10-1",
            age_category=Team.AgeCategory.X10,
        )
        player = Player.objects.create(
            first_name="Alice",
            last_name="Refsen",
            team=team_a,
            referee_certification=Player.RefereeCertification.F,
        )
        game = Game.objects.create(
            season=season,
            own_team=team_b,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(
            game=game,
            task_type=TaskType.REFEREE,
            slot_number=1,
        )
        TaskAssignment.objects.create(player=player, task=task)

        # No conflict yet
        response = api_client.get(f"/api/seasons/{season.id}/conflicts/")
        assert response.status_code == 200
        assert response.json() == []

        # Add away game for player's team
        Game.objects.create(
            season=season,
            own_team=team_a,
            opponent="Away Opponent",
            game_type=Game.GameType.AWAY,
            date=dt.date(2025, 10, 1),
            time=dt.time(10, 0),
            court=Game.Court.COURT_1,
        )

        # Now conflict should be detected
        response = api_client.get(f"/api/seasons/{season.id}/conflicts/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["player_name"] == "Alice Refsen"
        assert data[0]["reason"] == "Team has an away game on the same day"

    def test_conflict_response_fields(self, api_client, season):
        """Conflict response should contain all expected fields."""
        team_a = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        team_b = Team.objects.create(
            name="Vido X10-1",
            age_category=Team.AgeCategory.X10,
        )
        player = Player.objects.create(
            first_name="Bob",
            last_name="Timer",
            team=team_a,
        )
        game = Game.objects.create(
            season=season,
            own_team=team_b,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(game=game, task_type=TaskType.TIMER)
        assignment = TaskAssignment.objects.create(player=player, task=task)

        # Add home game for player's team at same time (different court)
        Game.objects.create(
            season=season,
            own_team=team_a,
            opponent="Home Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_2,
        )

        response = api_client.get(f"/api/seasons/{season.id}/conflicts/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        conflict = data[0]
        assert "assignment_id" in conflict
        assert "player_id" in conflict
        assert "player_name" in conflict
        assert "task_type" in conflict
        assert "game_id" in conflict
        assert "game_date" in conflict
        assert "game" in conflict
        assert "reason" in conflict
        assert conflict["assignment_id"] == assignment.id


@pytest.mark.django_db
class TestGameViewSetClearAssignments:
    def test_clear_assignments(self, api_client, season, team_x14, player):
        """Clear all assignments for a game."""
        game = Game.objects.create(
            season=season,
            own_team=team_x14,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(game=game, task_type=TaskType.SCORER)
        TaskAssignment.objects.create(player=player, task=task)

        response = api_client.post(f"/api/games/{game.id}/clear_assignments/")
        assert response.status_code == 200
        assert response.json()["cleared"] == 1
        assert TaskAssignment.objects.count() == 0


@pytest.mark.django_db
class TestTaskSuggestionsEndpoint:
    def test_suggestions(self, api_client, season):
        """Get candidate suggestions for a task."""
        team_a = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        team_b = Team.objects.create(
            name="Vido X10-1",
            age_category=Team.AgeCategory.X10,
        )
        Player.objects.create(
            first_name="Ref",
            last_name="Person",
            team=team_a,
            referee_certification=Player.RefereeCertification.F,
        )
        game = Game.objects.create(
            season=season,
            own_team=team_b,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(
            game=game,
            task_type=TaskType.REFEREE,
            slot_number=1,
        )

        response = api_client.get(f"/api/tasks/{task.id}/suggestions/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        player_names = {p["full_name"] for p in data}
        assert "Ref Person" in player_names

    def test_candidate_details(self, api_client, season):
        """Get detailed candidate info."""
        team_a = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        team_b = Team.objects.create(
            name="Vido X10-1",
            age_category=Team.AgeCategory.X10,
        )
        Player.objects.create(
            first_name="Ref",
            last_name="Person",
            team=team_a,
            referee_certification=Player.RefereeCertification.F,
        )
        game = Game.objects.create(
            season=season,
            own_team=team_b,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(
            game=game,
            task_type=TaskType.REFEREE,
            slot_number=1,
        )

        response = api_client.get(f"/api/tasks/{task.id}/candidate_details/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert "player" in data[0]
        assert "task_count" in data[0]
        assert "at_gym" in data[0]
        assert "suggestion_reason" in data[0]

    def test_team_eligibility(self, api_client, season):
        """Get team eligibility data."""
        team_a = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        team_b = Team.objects.create(
            name="Vido X10-1",
            age_category=Team.AgeCategory.X10,
        )
        Player.objects.create(
            first_name="Ref",
            last_name="Person",
            team=team_a,
            referee_certification=Player.RefereeCertification.F,
        )
        game = Game.objects.create(
            season=season,
            own_team=team_b,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(
            game=game,
            task_type=TaskType.REFEREE,
            slot_number=1,
        )

        response = api_client.get(f"/api/tasks/{task.id}/team_eligibility/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert "team" in data[0]
        assert "players" in data[0]
        assert "eligible_count" in data[0]
        assert "at_gym_day" in data[0]


@pytest.mark.django_db
class TestSiteConfig:
    def test_get_site_config(self, client):
        """GET is public (no auth needed) and returns club_name."""
        from hoops_planner.core.models import SiteConfig

        SiteConfig.objects.update_or_create(
            pk=1, defaults={"club_name": "BC Vido"}
        )
        response = client.get("/api/site-config/")
        assert response.status_code == 200
        assert response.json() == {"club_name": "BC Vido"}

    def test_put_site_config_requires_auth(self, client):
        """PUT without authentication is rejected."""
        response = client.put(
            "/api/site-config/",
            {"club_name": "New Name"},
            format="json",
        )
        assert response.status_code == 403

    def test_put_site_config_updates(self, api_client):
        """Authenticated PUT updates the club name."""
        response = api_client.put(
            "/api/site-config/",
            {"club_name": "Vido Basketball"},
            format="json",
        )
        assert response.status_code == 200
        assert response.json() == {"club_name": "Vido Basketball"}

        # Verify persistence
        from hoops_planner.core.models import SiteConfig

        assert SiteConfig.load().club_name == "Vido Basketball"
