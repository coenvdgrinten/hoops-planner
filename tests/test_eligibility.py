"""Tests for eligibility logic."""

import datetime as dt

import pytest

from sixth_man.core.eligibility import (
    get_eligible_players,
    get_eligible_players_with_indicator,
    is_eligible,
)
from sixth_man.core.models import (
    Game,
    Player,
    Task,
    TaskAssignment,
    TaskType,
    Team,
)


@pytest.mark.django_db
class TestAlreadyAssignedToGame:
    def test_eligible_when_no_assignments(self, player, task):
        assert is_eligible(player, task) is True

    def test_not_eligible_when_already_assigned(self, player, task):
        TaskAssignment.objects.create(player=player, task=task)
        assert is_eligible(player, task) is False

    def test_eligible_for_different_game(self, player, season):
        game1 = Game.objects.create(
            season=season,
            home_team=player.team,
            away_team="Team A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        game2 = Game.objects.create(
            season=season,
            home_team=player.team,
            away_team="Team B",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(16, 0),
            court=Game.Court.COURT_1,
        )
        task1 = Task.objects.create(game=game1, task_type=TaskType.SCORER)
        task2 = Task.objects.create(game=game2, task_type=TaskType.SCORER)
        TaskAssignment.objects.create(player=player, task=task1)
        assert is_eligible(player, task2) is True


@pytest.mark.django_db
class TestTeamHasHomeGameAtSameTime:
    def test_eligible_when_no_conflict(self, player, game, task):
        assert is_eligible(player, task) is True

    def test_not_eligible_when_team_has_home_game_at_same_time(self, player, season):
        # Player's team has a home game on Court 2 at same time
        Game.objects.create(
            season=season,
            home_team=player.team,
            away_team="Team A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        other_team = Team.objects.create(
            name="Vido X14-2",
            age_category=Team.AgeCategory.X14,
        )
        game = Game.objects.create(
            season=season,
            home_team=other_team,
            away_team="Team B",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_2,
        )
        task = Task.objects.create(game=game, task_type=TaskType.SCORER)
        assert is_eligible(player, task) is False

    def test_eligible_when_team_has_home_game_at_different_time(self, player, season):
        Game.objects.create(
            season=season,
            home_team=player.team,
            away_team="Team A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(16, 0),
            court=Game.Court.COURT_1,
        )
        game = Game.objects.create(
            season=season,
            home_team=player.team,
            away_team="Team B",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_2,
        )
        task = Task.objects.create(game=game, task_type=TaskType.SCORER)
        # Player is eligible for scorer on own team's game (no conflict)
        assert is_eligible(player, task) is True


@pytest.mark.django_db
class TestTeamHasAwayGameOnSameDay:
    def test_eligible_when_no_away_game(self, player, game, task):
        assert is_eligible(player, task) is True

    def test_not_eligible_when_team_has_away_game_same_day(self, player, season):
        Game.objects.create(
            season=season,
            home_team=player.team,
            away_team="Away Opponent",
            game_type=Game.GameType.AWAY,
            date=dt.date(2025, 10, 1),
            time=dt.time(10, 0),
            court=Game.Court.COURT_1,
        )
        game = Game.objects.create(
            season=season,
            home_team=player.team,
            away_team="Home Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(game=game, task_type=TaskType.SCORER)
        assert is_eligible(player, task) is False

    def test_eligible_when_away_game_different_day(self, player, season):
        Game.objects.create(
            season=season,
            home_team=player.team,
            away_team="Away Opponent",
            game_type=Game.GameType.AWAY,
            date=dt.date(2025, 10, 8),
            time=dt.time(10, 0),
            court=Game.Court.COURT_1,
        )
        game = Game.objects.create(
            season=season,
            home_team=player.team,
            away_team="Home Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        task = Task.objects.create(game=game, task_type=TaskType.SCORER)
        assert is_eligible(player, task) is True


@pytest.mark.django_db
class TestRefereeAgeCategoryRule:
    def test_eligible_when_player_team_same_age(self, referee, season):
        game = Game.objects.create(
            season=season,
            home_team=referee.team,
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
        assert is_eligible(referee, task) is True

    def test_eligible_when_player_team_higher_age(self, season):
        team = Team.objects.create(
            name="Vido X16-1",
            age_category=Team.AgeCategory.X16,
        )
        player = Player.objects.create(
            first_name="Older",
            last_name="Player",
            team=team,
            referee_certification=Player.RefereeCertification.T1,
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
        assert is_eligible(player, task) is True

    def test_not_eligible_when_player_team_lower_age(self, season):
        team = Team.objects.create(
            name="Vido X10-1",
            age_category=Team.AgeCategory.X10,
        )
        player = Player.objects.create(
            first_name="Young",
            last_name="Player",
            team=team,
            referee_certification=Player.RefereeCertification.T1,
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
        assert is_eligible(player, task) is False

    def test_rule_does_not_apply_to_non_referee_tasks(self, season):
        team = Team.objects.create(
            name="Vido X10-1",
            age_category=Team.AgeCategory.X10,
        )
        player = Player.objects.create(
            first_name="Young",
            last_name="Player",
            team=team,
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
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        assert is_eligible(player, task) is True


@pytest.mark.django_db
class TestRefereeCertificationRule:
    def test_not_eligible_referee_without_certification(self, player, game):
        task = Task.objects.create(
            game=game,
            task_type=TaskType.REFEREE,
            slot_number=1,
        )
        assert is_eligible(player, task) is False

    def test_eligible_referee_with_certification(self, referee, game):
        task = Task.objects.create(
            game=game,
            task_type=TaskType.REFEREE,
            slot_number=1,
        )
        assert is_eligible(referee, task) is True

    def test_rule_does_not_apply_to_non_referee_tasks(self, player, game):
        task = Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        assert is_eligible(player, task) is True


@pytest.mark.django_db
class TestCoachExemption:
    def test_coach_not_in_eligible_list(self, coach, task):
        eligible = get_eligible_players(task)
        assert coach not in eligible

    def test_coach_in_indicator_list(self, coach, task):
        results = get_eligible_players_with_indicator(task)
        names = [p.full_name for p, _ in results]
        assert coach.full_name in names


@pytest.mark.django_db
class TestGetEligiblePlayers:
    def test_returns_only_eligible(self, player, referee, season):
        # Player has no cert, referee does
        game_team = Team.objects.create(
            name="Vido X14-2",
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
        results = get_eligible_players(task)
        assert player not in results
        assert referee in results

    def test_empty_when_no_players(self, game):
        task = Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        Player.objects.all().delete()
        results = get_eligible_players(task)
        assert results == []


@pytest.mark.django_db
class TestCombinedRules:
    def test_multiple_disqualifications(self, season):
        # Player has home game at same time AND no cert — should be ineligible
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
        )
        player = Player.objects.create(
            first_name="John",
            last_name="Doe",
            team=team,
            referee_certification=Player.RefereeCertification.NONE,
        )
        # Player's team plays on Court 2 at same time
        Game.objects.create(
            season=season,
            home_team=team,
            away_team="Team A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_2,
        )
        other_team = Team.objects.create(
            name="Vido X14-2",
            age_category=Team.AgeCategory.X14,
        )
        game = Game.objects.create(
            season=season,
            home_team=other_team,
            away_team="Team B",
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
        assert is_eligible(player, task) is False
