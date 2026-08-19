"""Tests for statistics computation."""

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
from hoops_planner.core.statistics import (
    effective_multiplier_for,
    get_leaderboard,
    get_player_stats,
    get_season_stats,
    get_upcoming_assignments,
)


@pytest.mark.django_db
class TestGetPlayerStats:
    def test_zero_tasks(self, player):
        stats = get_player_stats(player)
        assert stats["total_tasks"] == 0
        assert stats["effective_tasks"] == 0.0
        assert stats["by_type"] == {}
        assert stats["games_with_own_team"] == 0
        assert stats["games_without_own_team"] == 0

    def test_task_with_own_team_game(self, player, season):
        # Player's team has a home game on the same date
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

        stats = get_player_stats(player)
        assert stats["total_tasks"] == 1
        assert stats["effective_tasks"] == 1.0
        assert stats["by_type"] == {"SCORER": 1}
        assert stats["games_with_own_team"] == 1
        assert stats["games_without_own_team"] == 0

    def test_task_without_own_team_game_2x_multiplier(self, player, season):
        # Another team's game — player's team has no game on this date
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

        stats = get_player_stats(player)
        assert stats["total_tasks"] == 1
        assert stats["effective_tasks"] == 2.0
        assert stats["games_with_own_team"] == 0
        assert stats["games_without_own_team"] == 1

    def test_away_day_multiplier_fields(self, player, season):
        # Another team's game — player's team has no game on this date
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

        stats = get_player_stats(player)
        # away_day_tasks counts the away-day assignment; away_day_bonus is the
        # extra effective point contributed by the 2x multiplier.
        assert stats["away_day_tasks"] == 1
        assert stats["away_day_bonus"] == 1.0
        expected = stats["total_tasks"] + stats["away_day_bonus"]
        assert stats["effective_tasks"] == expected

    def test_by_type_counts(self, player, season):
        game = Game.objects.create(
            season=season,
            own_team=player.team,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task_scorer = Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        task_timer = Task.objects.create(
            game=game,
            task_type=TaskType.TIMER,
            slot_number=1,
        )
        TaskAssignment.objects.create(player=player, task=task_scorer)
        TaskAssignment.objects.create(player=player, task=task_timer)

        stats = get_player_stats(player)
        assert stats["by_type"] == {"SCORER": 1, "TIMER": 1}

    def test_season_filter(self, player, season):
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

        # Filter by different season — should return zero
        other_season = Season.objects.create(name="2024-2025")
        stats = get_player_stats(player, other_season)
        assert stats["total_tasks"] == 0

        # Filter by same season — should return the task
        stats = get_player_stats(player, season)
        assert stats["total_tasks"] == 1


@pytest.mark.django_db
class TestEffectiveMultiplierFor:
    def test_single_when_own_team_has_game_that_date(self, player, season):
        Game.objects.create(
            season=season,
            own_team=player.team,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        assert effective_multiplier_for(player, dt.date(2025, 10, 1)) == 1

    def test_double_when_no_own_team_game_that_date(self, player, season):
        other_team = Team.objects.create(
            name="Vido X14-2",
            age_category=Team.AgeCategory.X14,
        )
        Game.objects.create(
            season=season,
            own_team=other_team,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        assert effective_multiplier_for(player, dt.date(2025, 10, 1)) == 2

    def test_counts_coached_teams(self, player, team_x14, season):
        # A different team the player coaches also makes the day "own"
        coached = Team.objects.create(
            name="Vido X10-2",
            age_category=Team.AgeCategory.X10,
        )
        player.coached_teams.add(coached)
        Game.objects.create(
            season=season,
            own_team=coached,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 2),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        assert effective_multiplier_for(player, dt.date(2025, 10, 2)) == 1
        assert effective_multiplier_for(player, dt.date(2025, 10, 3)) == 2


@pytest.mark.django_db
class TestGetSeasonStats:
    def test_empty_season(self, season):
        stats = get_season_stats(season)
        assert stats["total_games"] == 0
        assert stats["total_task_slots"] == 0
        assert stats["total_assignments"] == 0
        assert stats["fill_rate"] == 0.0
        assert stats["per_team"] == {}

    def test_fill_rate_calculation(self, season):
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

        stats = get_season_stats(season)
        assert stats["total_games"] == 1
        assert stats["total_task_slots"] == 1
        assert stats["total_assignments"] == 1
        assert stats["fill_rate"] == 100.0

    def test_by_task_type(self, season):
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
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
        Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        Task.objects.create(
            game=game,
            task_type=TaskType.TIMER,
            slot_number=1,
        )

        stats = get_season_stats(season)
        assert stats["by_task_type"]["SCORER"]["slots"] == 1
        assert stats["by_task_type"]["TIMER"]["slots"] == 1
        assert stats["by_task_type"]["SCORER"]["filled"] == 0

    def test_per_team(self, season):
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

        stats = get_season_stats(season)
        assert stats["per_team"]["Vido X14-1"]["games"] == 1
        assert stats["per_team"]["Vido X14-1"]["assignments"] == 1

    def test_per_team_attributes_away_games_to_travelling_team(self, season):
        # For an away game, own_team holds the club's travelling team.
        travelling = Team.objects.create(
            name="Vido X14-Away",
            age_category=Team.AgeCategory.X14,
        )
        game = Game.objects.create(
            season=season,
            own_team=travelling,
            opponent="External Opponent",
            game_type=Game.GameType.AWAY,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )

        stats = get_season_stats(season)
        # The fixture must be attributed to the travelling team, not the opponent.
        assert stats["per_team"]["Vido X14-Away"]["games"] == 1
        assert "Vido X14-Away" in stats["per_team"]


@pytest.mark.django_db
class TestGetUpcomingAssignments:
    def test_no_assignments(self, player):
        result = get_upcoming_assignments(player, after=dt.date(2025, 10, 1))
        assert result == []

    def test_returns_future_assignments(self, player, season):
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

        result = get_upcoming_assignments(player, after=dt.date(2026, 1, 1))
        assert len(result) == 1
        assert result[0]["game_date"] == "2027-01-01"
        assert result[0]["task_type"] == "SCORER"

    def test_excludes_past_assignments(self, player, season):
        game = Game.objects.create(
            season=season,
            own_team=player.team,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2020, 1, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        TaskAssignment.objects.create(player=player, task=task)

        result = get_upcoming_assignments(player, after=dt.date(2025, 1, 1))
        assert result == []

    def test_respects_limit(self, player, season):
        for i in range(5):
            game = Game.objects.create(
                season=season,
                own_team=player.team,
                opponent=f"Opponent {i}",
                game_type=Game.GameType.HOME,
                date=dt.date(2027, 1, i + 1),
                time=dt.time(14, 0),
                court=Game.Court.COURT_1,
            )
            task = Task.objects.create(
                game=game,
                task_type=TaskType.SCORER,
                slot_number=1,
            )
            TaskAssignment.objects.create(player=player, task=task)

        result = get_upcoming_assignments(player, after=dt.date(2026, 1, 1), limit=3)
        assert len(result) == 3


@pytest.mark.django_db
class TestGetLeaderboard:
    def test_empty_when_no_players(self, season):
        result = get_leaderboard(season)
        assert result == []

    def test_sorted_by_effective_tasks(self, season):
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        # Player with task on own team game (1x)
        player_a = Player.objects.create(
            first_name="Player",
            last_name="A",
            team=team,
        )
        game_a = Game.objects.create(
            season=season,
            own_team=team,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task_a = Task.objects.create(
            game=game_a,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        TaskAssignment.objects.create(player=player_a, task=task_a)

        # Player with task on away day (2x)
        other_team = Team.objects.create(
            name="Vido X14-2",
            age_category=Team.AgeCategory.X14,
        )
        player_b = Player.objects.create(
            first_name="Player",
            last_name="B",
            team=other_team,
        )
        game_b = Game.objects.create(
            season=season,
            own_team=team,  # different team's game
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 8),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task_b = Task.objects.create(
            game=game_b,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        TaskAssignment.objects.create(player=player_b, task=task_b)

        result = get_leaderboard(season)
        assert len(result) == 2
        assert result[0]["player_id"] == player_b.id  # 2.0 effective
        assert result[1]["player_id"] == player_a.id  # 1.0 effective

    def test_excludes_coaches(self, season):
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        coach = Player.objects.create(
            first_name="Coach",
            last_name="Name",
            team=team,
            is_coach=True,
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
        TaskAssignment.objects.create(player=coach, task=task)

        result = get_leaderboard(season)
        assert any(r["player_id"] == coach.id for r in result)

    def test_respects_top_limit(self, season):
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        players = []
        for i in range(5):
            p = Player.objects.create(
                first_name="Player",
                last_name=str(i),
                team=team,
            )
            players.append(p)
            game = Game.objects.create(
                season=season,
                own_team=team,
                opponent="Opponent",
                game_type=Game.GameType.HOME,
                date=dt.date(2025, 10, i + 1),
                time=dt.time(14, 0),
                court=Game.Court.COURT_1,
            )
            task = Task.objects.create(
                game=game,
                task_type=TaskType.SCORER,
                slot_number=1,
            )
            TaskAssignment.objects.create(player=p, task=task)

        result = get_leaderboard(season, top=3)
        assert len(result) == 3
