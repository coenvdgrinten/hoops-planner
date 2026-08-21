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
    get_team_eligibility,
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
            own_team=game_team,
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
            own_team=home_team,
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
            own_team=game_team,
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
            own_team=team_a,
            opponent="Opponent A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(12, 0),
            court=Game.Court.COURT_1,
        )
        # Task game at 14:00
        game = Game.objects.create(
            season=season,
            own_team=team_b,
            opponent="Opponent B",
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
            own_team=team_b,
            opponent="Opponent B",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        # Team A has a home game at 16:00 (after the task game)
        Game.objects.create(
            season=season,
            own_team=team_a,
            opponent="Opponent A",
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
            own_team=team_a,
            opponent="Opponent A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(10, 0),
            court=Game.Court.COURT_1,
        )
        # Task game at 14:00 — team_c is the home team (not team_a or team_b)
        game = Game.objects.create(
            season=season,
            own_team=team_c,
            opponent="Opponent C",
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
            own_team=team_a,
            opponent="Opponent A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(12, 0),
            court=Game.Court.COURT_1,
        )
        # Some other team plays at 14:30 on Court 2 (staggered)
        Game.objects.create(
            season=season,
            own_team=team_b,
            opponent="Opponent B",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 30),
            court=Game.Court.COURT_2,
        )
        # Task game at 14:00 on Court 1
        game = Game.objects.create(
            season=season,
            own_team=team_b,
            opponent="Opponent C",
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
            own_team=team_c,
            opponent="Old Opponent",
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
            own_team=team_c,
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
            own_team=team,
            opponent="Old Opponent",
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
            own_team=home_team,
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
        results = suggest_candidates(task)
        assert results[0] == player_low

    def test_same_day_task_counts_single_when_own_team_plays(self, season):
        # A player whose team plays on the target day must not get the 3x
        # same-day penalty for a task that day — they are at the gym
        # anyway, so the task counts single.
        team = Team.objects.create(
            name="Vido VSE-1",
            age_category=Team.AgeCategory.VSE,
        )
        player = Player.objects.create(
            first_name="Imke",
            last_name="Player",
            team=team,
        )
        # Her own team plays at 13:15 on the target day.
        Game.objects.create(
            season=season,
            own_team=team,
            opponent="Attacus VSE-1",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 9, 27),
            time=dt.time(13, 15),
            court=Game.Court.COURT_1,
        )
        # She referees another team's game earlier the same day (11:15).
        other_team = Team.objects.create(
            name="Vido X12-1",
            age_category=Team.AgeCategory.X12,
        )
        other_game = Game.objects.create(
            season=season,
            own_team=other_team,
            opponent="Achilles '71 X12-2",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 9, 27),
            time=dt.time(11, 15),
            court=Game.Court.COURT_2,
        )
        other_task = Task.objects.create(
            game=other_game,
            task_type=TaskType.REFEREE,
            slot_number=1,
        )
        TaskAssignment.objects.create(player=player, task=other_task)

        # Target: yet another team's game later the same day.
        target_team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        target_game = Game.objects.create(
            season=season,
            own_team=target_team,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 9, 27),
            time=dt.time(15, 15),
            court=Game.Court.COURT_1,
        )
        target_task = Task.objects.create(
            game=target_game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )

        details = get_candidate_details(target_task)
        found = [d for d in details if d[0] == player]
        assert len(found) == 1
        # Own team plays that day → the task counts 1x, not 3x.
        assert found[0][1] == 1.0

        # Same rule in the batched scorer used by the Teams & Members list.
        teams = get_team_eligibility(target_task)
        member = next(
            p
            for t in teams
            for p in t["players"]
            if p["player"] == player
        )
        assert member["task_count"] == 1.0

    def test_same_day_task_still_penalized_when_own_team_plays(self, season):
        # Regression: a player whose team plays later on the target day
        # already works a task earlier that day. Such a player must be
        # ranked below a free teammate who is equally "at the gym", even
        # though their own team plays that day (which makes the existing
        # task count single).
        #
        # Mirrors the reported bug: Thomas van Dongen (MSE-1, home game
        # 17:15) had a task at 15:15 yet was suggested first for the
        # 19:15 slot.
        busy_team = Team.objects.create(
            name="Vido MSE-1",
            age_category=Team.AgeCategory.MSE,
        )
        busy_player = Player.objects.create(
            first_name="Thomas",
            last_name="van Dongen",
            team=busy_team,
        )
        fresh_team = Team.objects.create(
            name="Vido MSE-2",
            age_category=Team.AgeCategory.MSE,
        )
        fresh_player = Player.objects.create(
            first_name="Free",
            last_name="Player",
            team=fresh_team,
        )
        # Both teams play at home on the target day, inside the 2h window
        # of the 19:15 target game.
        Game.objects.create(
            season=season,
            own_team=busy_team,
            opponent="Den Dunk MSE-1",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 5),
            time=dt.time(17, 15),
            court=Game.Court.COURT_1,
        )
        Game.objects.create(
            season=season,
            own_team=fresh_team,
            opponent="Venlo Sport Crusaders MSE-1",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 5),
            time=dt.time(17, 45),
            court=Game.Court.COURT_2,
        )
        # Busy player already works a task earlier the same day (15:15).
        other_team = Team.objects.create(
            name="Vido M18-1",
            age_category=Team.AgeCategory.M18,
        )
        other_game = Game.objects.create(
            season=season,
            own_team=other_team,
            opponent="BC Langstraat Shooters M18-2",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 5),
            time=dt.time(15, 15),
            court=Game.Court.COURT_1,
        )
        other_task = Task.objects.create(
            game=other_game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        TaskAssignment.objects.create(player=busy_player, task=other_task)

        # Target: a third team's game later the same day.
        target_team = Team.objects.create(
            name="Vido X14-2",
            age_category=Team.AgeCategory.X14,
        )
        target_game = Game.objects.create(
            season=season,
            own_team=target_team,
            opponent="OBC X14-2",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 5),
            time=dt.time(19, 15),
            court=Game.Court.COURT_1,
        )
        target_task = Task.objects.create(
            game=target_game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )

        results = suggest_candidates(target_task)
        # Both are "already at the gym"; the free player must outrank the
        # busy one via the ranking-only same-day penalty.
        assert results.index(fresh_player) < results.index(busy_player)

        # The displayed count stays honest: the busy player's task counts
        # single because their own team plays that day.
        details = {d[0]: d for d in get_candidate_details(target_task)}
        assert details[fresh_player][1] == 0.0
        assert details[busy_player][1] == 1.0


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
            own_team=team_a,
            opponent="Opponent A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(12, 0),
            court=Game.Court.COURT_1,
        )
        game = Game.objects.create(
            season=season,
            own_team=team_b,
            opponent="Opponent B",
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


@pytest.mark.django_db
class TestGetTeamEligibility:
    def test_returns_all_teams(self, season):
        team_a = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        team_b = Team.objects.create(
            name="Vido X10-1",
            age_category=Team.AgeCategory.X10,
        )
        Player.objects.create(first_name="PlayerA", last_name="Doe", team=team_a)
        Player.objects.create(first_name="PlayerB", last_name="Doe", team=team_b)
        home_team = Team.objects.create(
            name="Vido X16-1",
            age_category=Team.AgeCategory.X16,
        )
        game = Game.objects.create(
            season=season,
            own_team=home_team,
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
        results = get_team_eligibility(task)
        team_names = [r["team"].name for r in results]
        assert team_a.name in team_names
        assert team_b.name in team_names

    def test_team_player_details(self, season):
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        player = Player.objects.create(first_name="Player", last_name="Doe", team=team)
        home_team = Team.objects.create(
            name="Vido X16-1",
            age_category=Team.AgeCategory.X16,
        )
        game = Game.objects.create(
            season=season,
            own_team=home_team,
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
        results = get_team_eligibility(task)
        team_result = [r for r in results if r["team"] == team][0]
        assert len(team_result["players"]) == 1
        p_info = team_result["players"][0]
        assert p_info["player"] == player
        assert p_info["eligible"] is True
        assert p_info["task_count"] == 0

    def test_exempt_player_not_eligible(self, season):
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        Player.objects.create(
            first_name="Exempt", last_name="Player", team=team, is_exempt=True
        )
        home_team = Team.objects.create(
            name="Vido X16-1",
            age_category=Team.AgeCategory.X16,
        )
        game = Game.objects.create(
            season=season,
            own_team=home_team,
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
        results = get_team_eligibility(task)
        team_result = [r for r in results if r["team"] == team][0]
        p_info = team_result["players"][0]
        assert p_info["eligible"] is False
        assert team_result["eligible_count"] == 0

    def test_eligible_count_correct(self, season):
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        Player.objects.create(first_name="Eligible", last_name="Player", team=team)
        Player.objects.create(
            first_name="Exempt", last_name="Player", team=team, is_exempt=True
        )
        home_team = Team.objects.create(
            name="Vido X16-1",
            age_category=Team.AgeCategory.X16,
        )
        game = Game.objects.create(
            season=season,
            own_team=home_team,
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
        results = get_team_eligibility(task)
        team_result = [r for r in results if r["team"] == team][0]
        assert team_result["eligible_count"] == 1

    def test_at_gym_flag_in_team_eligibility(self, season):
        team_a = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        Player.objects.create(first_name="AtGym", last_name="Player", team=team_a)
        # Team A has a game adjacent to the task game
        Game.objects.create(
            season=season,
            own_team=team_a,
            opponent="Opponent A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(12, 0),
            court=Game.Court.COURT_1,
        )
        home_team = Team.objects.create(
            name="Vido X16-1",
            age_category=Team.AgeCategory.X16,
        )
        game = Game.objects.create(
            season=season,
            own_team=home_team,
            opponent="Opponent B",
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
        results = get_team_eligibility(task)
        team_result = [r for r in results if r["team"] == team_a][0]
        p_info = team_result["players"][0]
        assert p_info["at_gym"] == "before"  # Returns position string, not bool


@pytest.mark.django_db
class TestParentSuggestionBonus:
    """Parents filling scorer/timer for their own kid's team get a ranking
    bonus (a nudge), but a lighter non-parent can still outrank them."""

    def _busy_day(self, season):
        """Kid team plays at 14:00; six other teams have adjacent home games."""
        kid = Team.objects.create(
            name="Vido X10-1",
            age_category=Team.AgeCategory.X10,
            parent_responsible=True,
        )
        parents = [
            Player.objects.create(first_name=f"P{i}", last_name="Parent", team=kid)
            for i in range(3)
        ]
        slots = [
            (dt.time(12, 0), Game.Court.COURT_1),
            (dt.time(13, 0), Game.Court.COURT_1),
            (dt.time(13, 0), Game.Court.COURT_2),
            (dt.time(15, 0), Game.Court.COURT_1),
            (dt.time(16, 0), Game.Court.COURT_1),
            (dt.time(16, 0), Game.Court.COURT_2),
        ]
        for i, (slot_time, slot_court) in enumerate(slots):
            t = Team.objects.create(
                name=f"Vido X14-{i + 1}", age_category=Team.AgeCategory.X14
            )
            for j in range(3):
                Player.objects.create(
                    first_name=f"O{i}_{j}", last_name="Other", team=t
                )
            Game.objects.create(
                season=season,
                own_team=t,
                opponent="Opp",
                game_type=Game.GameType.HOME,
                date=dt.date(2025, 10, 1),
                time=slot_time,
                court=slot_court,
            )
        game = Game.objects.create(
            season=season,
            own_team=kid,
            opponent="Opp",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(
            game=game, task_type=TaskType.SCORER, slot_number=1
        )
        return kid, parents, task

    def test_parent_preferred_at_equal_load(self, season):
        kid, parents, task = self._busy_day(season)
        details = get_candidate_details(task, limit=100)
        ranks = {d[0].id: i for i, d in enumerate(details)}
        # All candidates are zero-count and at the gym; the parent bonus must
        # pull every parent ahead of every non-parent.
        parent_ranks = sorted(ranks[p.id] for p in parents)
        non_parent_ranks = [
            i for i, d in enumerate(details) if d[0].team_id != kid.id
        ]
        assert max(parent_ranks) < min(non_parent_ranks)

    def test_lighter_non_parent_still_outranks_heavy_parent(self, season):
        kid, parents, task = self._busy_day(season)
        heavy_parent = parents[0]
        # Give the heavy parent several away-day tasks (2x each).
        filler = Team.objects.create(
            name="Vido M16-1", age_category=Team.AgeCategory.M16
        )
        for k in range(3):
            g = Game.objects.create(
                season=season,
                own_team=filler,
                opponent=f"Old{k}",
                game_type=Game.GameType.HOME,
                date=dt.date(2025, 9, 1 + k),
                time=dt.time(14, 0),
                court=Game.Court.COURT_1,
            )
            t = Task.objects.create(game=g, task_type=TaskType.SCORER, slot_number=1)
            TaskAssignment.objects.create(player=heavy_parent, task=t)

        details = get_candidate_details(task, limit=100)
        order = [d[0] for d in details]
        # A zero-load non-parent must rank above the heavily loaded parent.
        light = next(
            p for p in order if p.team_id != kid.id and p.assignments.count() == 0
        )
        assert order.index(light) < order.index(heavy_parent)

    def test_no_bonus_for_referee_task(self, season):
        kid, parents, scorer_task = self._busy_day(season)
        # Give every player an F-diploma so referees are uniformly eligible.
        for p in Player.objects.all():
            p.referee_certification = Player.RefereeCertification.F
            p.save(update_fields=["referee_certification"])
        referee_task = Task.objects.create(
            game=scorer_task.game, task_type=TaskType.REFEREE, slot_number=1
        )
        details = get_candidate_details(referee_task, limit=100)
        # No parent bonus applies to refereeing — no special reason label.
        reasons = {d[3] for d in details}
        assert "Parent of this team" not in reasons

    def test_parent_reason_label(self, season):
        kid, parents, task = self._busy_day(season)
        details = get_candidate_details(task, limit=100)
        parent_reasons = [d[3] for d in details if d[0].team_id == kid.id]
        assert parent_reasons
        assert all(r == "Parent of this team" for r in parent_reasons)
