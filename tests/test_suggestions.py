"""Tests for suggestion logic."""

import datetime as dt

import pytest

from hoops_planner.core.models import (
    Game,
    Player,
    Task,
    TaskAssignment,
    TaskType,
    Team,
)
from hoops_planner.core.suggestions import (
    get_candidate_details,
    suggest_candidates,
)


@pytest.mark.django_db
class TestSuggestCandidates:
    def test_returns_eligible_players(self, player, task):
        results = suggest_candidates(task)
        assert player in results

    def test_excludes_ineligible_players(self, season):
        # Young player ineligible for refereeing
        young_team = Team.objects.create(
            name="Vido X10-1",
            age_category=Team.AgeCategory.X10,
        )
        young_player = Player.objects.create(
            first_name="Young",
            last_name="Player",
            team=young_team,
            referee_certification=Player.RefereeCertification.F,
        )
        game_team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        game = Game.objects.create(
            season=season,
            home_team=game_team,
            away_team="Opponent",
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
        results = suggest_candidates(task)
        assert young_player not in results

    def test_includes_coaches(self, coach, task):
        """Coaches can be voluntarily assigned so they appear in candidates."""
        results = suggest_candidates(task)
        assert coach in results

    def test_respects_limit(self, season):
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        players = []
        for i in range(10):
            p = Player.objects.create(
                first_name=f"Player{i}",
                last_name="Doe",
                team=team,
            )
            players.append(p)
        home_team = Team.objects.create(
            name="Vido X10-1",
            age_category=Team.AgeCategory.X10,
        )
        game = Game.objects.create(
            season=season,
            home_team=home_team,
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
        results = suggest_candidates(task, limit=3)
        assert len(results) == 3

    def test_empty_when_no_eligible(self, season):
        # Only a young player exists, task is refereeing for older team
        young_team = Team.objects.create(
            name="Vido X10-1",
            age_category=Team.AgeCategory.X10,
        )
        Player.objects.create(
            first_name="Young",
            last_name="Player",
            team=young_team,
            referee_certification=Player.RefereeCertification.F,
        )
        game_team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        game = Game.objects.create(
            season=season,
            home_team=game_team,
            away_team="Opponent",
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
        results = suggest_candidates(task)
        assert results == []


@pytest.mark.django_db
class TestAlreadyAtGymPriority:
    def test_player_at_gym_ranked_first(self, season):
        # Team A plays at 12:00 (before), Team B plays at 14:00 (the task game)
        team_a = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        team_b = Team.objects.create(
            name="Vido X14-2",
            age_category=Team.AgeCategory.X14,
        )
        player_at_gym = Player.objects.create(
            first_name="AtGym",
            last_name="Player",
            team=team_a,
        )
        Player.objects.create(
            first_name="NotAtGym",
            last_name="Player",
            team=team_b,
        )
        # Team A has a home game at 12:00 (before the task game)
        Game.objects.create(
            season=season,
            home_team=team_a,
            away_team="Opponent A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(12, 0),
            court=Game.Court.COURT_1,
        )
        # Task game at 14:00
        game = Game.objects.create(
            season=season,
            home_team=team_b,
            away_team="Opponent B",
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
        results = suggest_candidates(task)
        assert results[0] == player_at_gym

    def test_player_at_gym_after_also_priority(self, season):
        team_a = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        team_b = Team.objects.create(
            name="Vido X14-2",
            age_category=Team.AgeCategory.X14,
        )
        player_at_gym = Player.objects.create(
            first_name="AtGym",
            last_name="Player",
            team=team_a,
        )
        Player.objects.create(
            first_name="NotAtGym",
            last_name="Player",
            team=team_b,
        )
        # Task game at 14:00
        game = Game.objects.create(
            season=season,
            home_team=team_b,
            away_team="Opponent B",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        # Team A has a home game at 16:00 (after the task game)
        Game.objects.create(
            season=season,
            home_team=team_a,
            away_team="Opponent A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(16, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        results = suggest_candidates(task)
        assert results[0] == player_at_gym

    def test_player_not_at_gym_when_outside_window(self, season):
        """Player's team plays at 10:00 — outside the 2-hour window of 14:00."""
        team_a = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        team_b = Team.objects.create(
            name="Vido X14-2",
            age_category=Team.AgeCategory.X14,
        )
        team_c = Team.objects.create(
            name="Vido X14-3",
            age_category=Team.AgeCategory.X14,
        )
        player_a = Player.objects.create(
            first_name="PlayerA",
            last_name="Doe",
            team=team_a,
        )
        Player.objects.create(
            first_name="PlayerB",
            last_name="Doe",
            team=team_b,
        )
        # Team A plays at 10:00 — 4 hours before the task game at 14:00
        Game.objects.create(
            season=season,
            home_team=team_a,
            away_team="Opponent A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(10, 0),
            court=Game.Court.COURT_1,
        )
        # Task game at 14:00 — team_c is the home team (not team_a or team_b)
        game = Game.objects.create(
            season=season,
            home_team=team_c,
            away_team="Opponent C",
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
        # Player A is not at gym (10:00 is 4 hours before 14:00, outside 2h window)
        # So player_a should NOT have an adjacent game position — check via details.
        from hoops_planner.core.suggestions import get_candidate_details

        details = get_candidate_details(task)
        player_a_details = [d for d in details if d[0] == player_a]
        assert len(player_a_details) == 1
        assert player_a_details[0][2] is None  # no adjacent game position

    def test_staggered_times_still_work(self, season):
        """Staggered game times don't break the time window."""
        team_a = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        team_b = Team.objects.create(
            name="Vido X14-2",
            age_category=Team.AgeCategory.X14,
        )
        player_at_gym = Player.objects.create(
            first_name="AtGym",
            last_name="Player",
            team=team_a,
        )
        Player.objects.create(
            first_name="NotAtGym",
            last_name="Player",
            team=team_b,
        )
        # Team A plays at 12:00 on Court 1
        Game.objects.create(
            season=season,
            home_team=team_a,
            away_team="Opponent A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(12, 0),
            court=Game.Court.COURT_1,
        )
        # Some other team plays at 14:30 on Court 2 (staggered)
        Game.objects.create(
            season=season,
            home_team=team_b,
            away_team="Opponent B",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 30),
            court=Game.Court.COURT_2,
        )
        # Task game at 14:00 on Court 1
        game = Game.objects.create(
            season=season,
            home_team=team_b,
            away_team="Opponent C",
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
        results = suggest_candidates(task)
        # Player at gym (12:00 is within 2h of 14:00), staggered 14:30 doesn't matter
        assert results[0] == player_at_gym


@pytest.mark.django_db
class TestTaskCounterTiebreaker:
    def test_lower_task_count_ranked_first(self, season):
        team_a = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        team_b = Team.objects.create(
            name="Vido X14-2",
            age_category=Team.AgeCategory.X14,
        )
        team_c = Team.objects.create(
            name="Vido X14-3",
            age_category=Team.AgeCategory.X14,
        )
        player_zero = Player.objects.create(
            first_name="Zero",
            last_name="Doe",
            team=team_a,
        )
        player_one = Player.objects.create(
            first_name="One",
            last_name="Doe",
            team=team_b,
        )
        # Give player_one an existing assignment
        other_game = Game.objects.create(
            season=season,
            home_team=team_c,
            away_team="Old Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 9, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        other_task = Task.objects.create(
            game=other_game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        TaskAssignment.objects.create(player=player_one, task=other_task)

        game = Game.objects.create(
            season=season,
            home_team=team_c,
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
        results = suggest_candidates(task)
        assert results[0] == player_zero

    def test_away_day_multiplier_affects_count(self, season):
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        player_low = Player.objects.create(
            first_name="Low",
            last_name="Doe",
            team=team,
        )
        player_high = Player.objects.create(
            first_name="High",
            last_name="Doe",
            team=team,
        )
        # player_high has a task on a day with no game (2x multiplier)
        other_game = Game.objects.create(
            season=season,
            home_team=team,
            away_team="Old Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 9, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        other_task = Task.objects.create(
            game=other_game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        TaskAssignment.objects.create(player=player_high, task=other_task)
        # No game for player_high's team on Sept 1 — multiplier applies
        # Effective count = 2.0 for player_high, 0.0 for player_low

        home_team = Team.objects.create(
            name="Vido X10-1",
            age_category=Team.AgeCategory.X10,
        )
        game = Game.objects.create(
            season=season,
            home_team=home_team,
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
        results = suggest_candidates(task)
        assert results[0] == player_low


@pytest.mark.django_db
class TestGetCandidateDetails:
    def test_returns_correct_details(self, player, task):
        details = get_candidate_details(task)
        found = [d for d in details if d[0] == player]
        assert len(found) == 1
        assert found[0][1] == 0.0  # task count
        assert found[0][2] is None  # no adjacent game (player's team not involved)

    def test_at_gym_flag_correct(self, season):
        team_a = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        team_b = Team.objects.create(
            name="Vido X14-2",
            age_category=Team.AgeCategory.X14,
        )
        player = Player.objects.create(
            first_name="AtGym",
            last_name="Player",
            team=team_a,
        )
        # Team A plays at 12:00 (adjacent to 14:00)
        Game.objects.create(
            season=season,
            home_team=team_a,
            away_team="Opponent A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(12, 0),
            court=Game.Court.COURT_1,
        )
        game = Game.objects.create(
            season=season,
            home_team=team_b,
            away_team="Opponent B",
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
        details = get_candidate_details(task)
        found = [d for d in details if d[0] == player]
        assert (
            found[0][2] == "before"
        )  # at gym (player's game is before the task's game)
