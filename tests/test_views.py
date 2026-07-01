"""Tests for API views."""

import datetime as dt

import pytest

from sixth_man.core.models import (
    Game,
    Player,
    Season,
    Task,
    TaskAssignment,
    TaskType,
    Team,
)


@pytest.mark.django_db
class TestGameViewSet:
    def test_list_games_without_season_filter(self, api_client, season):
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        Game.objects.create(
            season=season,
            home_team=team,
            away_team="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        other_season = Season.objects.create(name="2024-2025")
        Game.objects.create(
            season=other_season,
            home_team=team,
            away_team="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_2,
        )

        response = api_client.get("/api/games/")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_games_with_season_filter(self, api_client, season):
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        Game.objects.create(
            season=season,
            home_team=team,
            away_team="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        other_season = Season.objects.create(name="2024-2025")
        Game.objects.create(
            season=other_season,
            home_team=team,
            away_team="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_2,
        )

        response = api_client.get(f"/api/games/?season={season.id}")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_tasks_with_assignments(self, api_client, player, season):
        game = Game.objects.create(
            season=season,
            home_team=player.team,
            away_team="Opponent",
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
            home_team=player.team,
            away_team="Opponent",
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
            home_team=player.team,
            away_team="Opponent",
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
            home_team=team,
            away_team="Opponent",
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
            home_team=team,
            away_team="Opponent",
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
            home_team=player.team,
            away_team="Opponent",
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
