"""Tests for gym reservation coverage logic."""

import datetime as dt

import pytest

from hoops_planner.core.gym_coverage import get_gym_coverage
from hoops_planner.core.models import Game, GymReservation, SiteConfig, Team


@pytest.fixture
def team():
    return Team.objects.create(name="Vido X14-1", age_category="X14")


@pytest.fixture
def home_game(season, team):
    return Game.objects.create(
        season=season,
        own_team=team,
        opponent="Achilles '71",
        game_type=Game.GameType.HOME,
        date=dt.date(2025, 10, 1),
        time=dt.time(14, 0),
        court="1",
    )


@pytest.fixture
def away_game(season, team):
    return Game.objects.create(
        season=season,
        own_team=team,
        opponent="Quickpoint",
        game_type=Game.GameType.AWAY,
        date=dt.date(2025, 10, 3),
        time=dt.time(18, 0),
        court="1",
    )


@pytest.fixture
def full_day_reservation(season):
    return GymReservation.objects.create(
        season=season,
        date=dt.date(2025, 10, 1),
        start_time=dt.time(9, 0),
        end_time=dt.time(20, 0),
    )


@pytest.mark.django_db
class TestGymCoverageBasic:
    def test_no_games_no_reservations(self, season):
        result = get_gym_coverage(season)
        assert result["total_home_games"] == 0
        assert result["covered_games"] == 0
        assert result["uncovered_games"] == []
        assert result["surplus"] == []

    def test_no_reservations_all_uncovered(self, season, home_game):
        result = get_gym_coverage(season)
        assert result["total_home_games"] == 1
        assert result["covered_games"] == 0
        assert len(result["uncovered_games"]) == 1
        assert result["uncovered_games"][0]["game_id"] == home_game.id

    def test_full_coverage(self, season, home_game, full_day_reservation):
        result = get_gym_coverage(season)
        assert result["total_home_games"] == 1
        assert result["covered_games"] == 1
        assert result["uncovered_games"] == []

    def test_away_games_excluded(
        self, season, home_game, away_game, full_day_reservation
    ):
        result = get_gym_coverage(season)
        assert result["total_home_games"] == 1

    def test_uncovered_game_details(self, season, home_game):
        result = get_gym_coverage(season)
        g = result["uncovered_games"][0]
        assert g["date"] == "2025-10-01"
        assert g["time"] == "14:00"
        assert g["own_team"] == "Vido X14-1"
        assert g["opponent"] == "Achilles '71"
        # Default: 90min game, 30min before, 15min after
        # Required: 13:30 - 15:45
        assert g["required_start"] == "13:30"
        assert g["required_end"] == "15:45"


@pytest.mark.django_db
class TestGymCoverageMargins:
    def test_exact_fit_is_covered(self, season, home_game):
        # Required window: 13:30 - 15:45 (90min game + 30 before + 15 after)
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(13, 30),
            end_time=dt.time(15, 45),
        )
        result = get_gym_coverage(season)
        assert result["covered_games"] == 1

    def test_one_minute_short_is_uncovered(self, season, home_game):
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(13, 30),
            end_time=dt.time(15, 44),
        )
        result = get_gym_coverage(season)
        assert result["covered_games"] == 0
        assert len(result["uncovered_games"]) == 1

    def test_one_minute_early_start_is_covered(self, season, home_game):
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(13, 29),
            end_time=dt.time(15, 45),
        )
        result = get_gym_coverage(season)
        assert result["covered_games"] == 1

    def test_zero_margins(self, season, home_game):
        config = SiteConfig.load()
        config.gym_margin_before_minutes = 0
        config.gym_margin_after_minutes = 0
        config.save()

        # Required window is just the game: 14:00 - 15:30
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(14, 0),
            end_time=dt.time(15, 30),
        )
        result = get_gym_coverage(season)
        assert result["covered_games"] == 1

    def test_custom_duration(self, season, home_game):
        config = SiteConfig.load()
        config.gym_game_duration_minutes = 60
        config.save()

        # Required: 13:30 - 15:15 (60min game + 30 before + 15 after)
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(13, 30),
            end_time=dt.time(15, 15),
        )
        result = get_gym_coverage(season)
        assert result["covered_games"] == 1

    def test_multiple_reservations_one_covers(self, season, home_game):
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(8, 0),
            end_time=dt.time(10, 0),
        )
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(13, 0),
            end_time=dt.time(17, 0),
        )
        result = get_gym_coverage(season)
        assert result["covered_games"] == 1

    def test_two_games_same_day_one_reservation(
        self, season, team, full_day_reservation
    ):
        Game.objects.create(
            season=season,
            own_team=team,
            opponent="Team A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(10, 0),
            court="1",
        )
        Game.objects.create(
            season=season,
            own_team=team,
            opponent="Team B",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(17, 0),
            court="2",
        )
        result = get_gym_coverage(season)
        assert result["total_home_games"] == 2
        assert result["covered_games"] == 2


@pytest.mark.django_db
class TestGymCoverageSurplus:
    def test_empty_reservation_full_surplus(self, season):
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(17, 0),
        )
        result = get_gym_coverage(season)
        assert len(result["surplus"]) == 1
        s = result["surplus"][0]
        assert s["start"] == "09:00"
        assert s["end"] == "17:00"
        assert s["minutes"] == 480

    def test_surplus_around_game(self, season, home_game, full_day_reservation):
        # Reservation 09:00-20:00, game needs 13:30-15:45
        # Surplus: 09:00-13:30 (270min) and 15:45-20:00 (255min)
        result = get_gym_coverage(season)
        assert len(result["surplus"]) == 2
        starts = [s["start"] for s in result["surplus"]]
        assert "09:00" in starts
        assert "15:45" in starts

    def test_small_gap_below_threshold_not_reported(self, season, home_game):
        # Reservation 13:30-16:10, game needs 13:30-16:00
        # Gap is only 10 min (< 30 min threshold)
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(13, 30),
            end_time=dt.time(16, 10),
        )
        result = get_gym_coverage(season)
        assert result["surplus"] == []

    def test_gap_between_two_games(self, season, team):
        Game.objects.create(
            season=season,
            own_team=team,
            opponent="A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(10, 0),
            court="1",
        )
        Game.objects.create(
            season=season,
            own_team=team,
            opponent="B",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(16, 0),
            court="1",
        )
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(18, 0),
        )
        result = get_gym_coverage(season)
        # Game 1 window: 09:30-11:45, Game 2 window: 15:30-17:45
        # Gap: 11:45-15:30 = 225 min
        gaps = [s for s in result["surplus"] if s["minutes"] >= 30]
        assert any(s["start"] == "11:45" and s["end"] == "15:30" for s in gaps)

    def test_surplus_only_for_matching_date(self, season, home_game):
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 5),
            start_time=dt.time(9, 0),
            end_time=dt.time(17, 0),
        )
        result = get_gym_coverage(season)
        # The Oct 5 reservation has no games → full surplus
        assert len(result["surplus"]) == 1
        assert result["surplus"][0]["date"] == "2025-10-05"


@pytest.mark.django_db
class TestGymCoverageBoundaries:
    def test_window_spanning_two_reservations_not_covered(self, season, home_game):
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(13, 0),
            end_time=dt.time(14, 30),
        )
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(14, 30),
            end_time=dt.time(16, 0),
        )
        result = get_gym_coverage(season)
        assert result["covered_games"] == 0
        assert len(result["uncovered_games"]) == 1

    def test_mixed_coverage_same_day(self, season, team):
        Game.objects.create(
            season=season, own_team=team, opponent="A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1), time=dt.time(14, 0), court="1",
        )
        g2 = Game.objects.create(
            season=season, own_team=team, opponent="B",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1), time=dt.time(17, 0), court="2",
        )
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(16, 0),
        )
        result = get_gym_coverage(season)
        assert result["total_home_games"] == 2
        assert result["covered_games"] == 1
        assert result["uncovered_games"][0]["game_id"] == g2.id

    def test_reservation_on_different_date_does_not_cover(self, season, home_game):
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 2),
            start_time=dt.time(9, 0),
            end_time=dt.time(20, 0),
        )
        result = get_gym_coverage(season)
        assert result["covered_games"] == 0
        assert len(result["uncovered_games"]) == 1

    def test_midnight_game_required_start_rolls_to_previous_day(self, season, team):
        Game.objects.create(
            season=season, own_team=team, opponent="A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1), time=dt.time(0, 0), court="1",
        )
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(0, 0),
            end_time=dt.time(3, 0),
        )
        result = get_gym_coverage(season)
        assert result["covered_games"] == 0
        assert result["uncovered_games"][0]["required_start"] == "23:30"

    def test_late_night_game_required_end_passes_midnight(self, season, team):
        Game.objects.create(
            season=season, own_team=team, opponent="A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1), time=dt.time(23, 59), court="1",
        )
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(22, 0),
            end_time=dt.time(23, 59),
        )
        result = get_gym_coverage(season)
        assert result["covered_games"] == 0
        assert result["uncovered_games"][0]["required_end"] == "01:44"

    def test_uncovered_list_ordered_by_date_then_time(self, season, team):
        Game.objects.create(
            season=season, own_team=team, opponent="Later",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 5), time=dt.time(10, 0), court="1",
        )
        Game.objects.create(
            season=season, own_team=team, opponent="Earlier",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1), time=dt.time(14, 0), court="1",
        )
        result = get_gym_coverage(season)
        assert result["uncovered_games"][0]["date"] == "2025-10-01"
        assert result["uncovered_games"][1]["date"] == "2025-10-05"

    def test_away_only_season(self, season, team):
        Game.objects.create(
            season=season, own_team=team, opponent="Quickpoint",
            game_type=Game.GameType.AWAY,
            date=dt.date(2025, 10, 1), time=dt.time(14, 0), court="1",
        )
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(17, 0),
        )
        result = get_gym_coverage(season)
        assert result["total_home_games"] == 0
        assert result["covered_games"] == 0
        assert result["uncovered_games"] == []
        assert len(result["surplus"]) == 1
        assert result["surplus"][0]["minutes"] == 480

    def test_two_games_same_time_same_date(self, season, team):
        Game.objects.create(
            season=season, own_team=team, opponent="A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1), time=dt.time(14, 0), court="1",
        )
        Game.objects.create(
            season=season, own_team=team, opponent="B",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1), time=dt.time(14, 0), court="2",
        )
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(20, 0),
        )
        result = get_gym_coverage(season)
        assert result["total_home_games"] == 2
        assert result["covered_games"] == 2
        assert len(result["surplus"]) == 2

    def test_many_games_and_reservations(self, season, team):
        for day in range(1, 6):
            Game.objects.create(
                season=season, own_team=team, opponent=f"Team {day}",
                game_type=Game.GameType.HOME,
                date=dt.date(2025, 10, day), time=dt.time(14, 0), court="1",
            )
            GymReservation.objects.create(
                season=season,
                date=dt.date(2025, 10, day),
                start_time=dt.time(13, 30),
                end_time=dt.time(15, 45),
            )
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 11, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(17, 0),
        )
        result = get_gym_coverage(season)
        assert result["covered_games"] == 5
        assert result["total_home_games"] == 5
        assert result["uncovered_games"] == []
        assert len(result["surplus"]) == 1
        assert result["surplus"][0]["minutes"] == 480
        assert result["surplus"][0]["date"] == "2025-11-01"


@pytest.mark.django_db
class TestGymCoverageSurplusEdges:
    def test_reservation_exactly_matches_game_window(
        self, season, home_game
    ):
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(13, 30),
            end_time=dt.time(15, 45),
        )
        result = get_gym_coverage(season)
        assert result["surplus"] == []

    def test_adjacent_game_windows_no_gap_between(self, season, team):
        Game.objects.create(
            season=season, own_team=team, opponent="A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1), time=dt.time(10, 0), court="1",
        )
        Game.objects.create(
            season=season, own_team=team, opponent="B",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1), time=dt.time(12, 15), court="1",
        )
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 30),
            end_time=dt.time(14, 0),
        )
        result = get_gym_coverage(season)
        assert result["surplus"] == []

    def test_game_window_extends_beyond_reservation_end(self, season, home_game):
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(13, 0),
            end_time=dt.time(15, 0),
        )
        result = get_gym_coverage(season)
        assert result["covered_games"] == 0
        assert len(result["surplus"]) == 1
        assert result["surplus"][0]["start"] == "13:00"
        assert result["surplus"][0]["end"] == "13:30"
        assert result["surplus"][0]["minutes"] == 30

    def test_game_window_starts_before_reservation(self, season, home_game):
        # Game 14:00, window 13:30-15:45. Reservation 14:00-18:00.
        # Cursor starts at 14:00, window end clamps to 15:45.
        # Trailing gap: 15:45-18:00 = 135 min.
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(14, 0),
            end_time=dt.time(18, 0),
        )
        result = get_gym_coverage(season)
        assert len(result["surplus"]) == 1
        assert result["surplus"][0]["start"] == "15:45"
        assert result["surplus"][0]["end"] == "18:00"
        assert result["surplus"][0]["minutes"] == 135

    def test_overlapping_game_windows(self, season, team):
        # Game 10:00 → window 09:30-11:45
        # Game 11:00 → window 10:30-12:45
        # Overlap: 10:30-11:45. Merged effective span: 09:30-12:45.
        Game.objects.create(
            season=season, own_team=team, opponent="A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1), time=dt.time(10, 0), court="1",
        )
        Game.objects.create(
            season=season, own_team=team, opponent="B",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1), time=dt.time(11, 0), court="1",
        )
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(14, 0),
        )
        result = get_gym_coverage(season)
        assert len(result["surplus"]) == 2
        assert result["surplus"][0]["start"] == "09:00"
        assert result["surplus"][0]["end"] == "09:30"
        assert result["surplus"][0]["minutes"] == 30
        assert result["surplus"][1]["start"] == "12:45"
        assert result["surplus"][1]["end"] == "14:00"
        assert result["surplus"][1]["minutes"] == 75

    def test_multiple_reservations_same_date_later_game_truncates_earlier(
        self, season, home_game
    ):
        res_a = GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(11, 0),
        )
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(13, 30),
            end_time=dt.time(15, 45),
        )
        result = get_gym_coverage(season)
        entries = [s for s in result["surplus"] if s["reservation_id"] == res_a.id]
        assert len(entries) == 1
        assert entries[0]["start"] == "09:00"
        assert entries[0]["end"] == "13:30"
        assert entries[0]["minutes"] == 270

    def test_tiny_reservation_below_threshold(self, season):
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(9, 10),
        )
        result = get_gym_coverage(season)
        assert result["surplus"] == []

    def test_gap_exactly_30_minutes_reported(self, season):
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(9, 30),
        )
        result = get_gym_coverage(season)
        assert len(result["surplus"]) == 1
        assert result["surplus"][0]["minutes"] == 30

    def test_gap_29_minutes_not_reported(self, season):
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(9, 29),
        )
        result = get_gym_coverage(season)
        assert result["surplus"] == []

    def test_three_games_produce_four_gaps(self, season, team):
        for t, opp in [(10, "A"), (14, "B"), (17, "C")]:
            Game.objects.create(
                season=season, own_team=team, opponent=opp,
                game_type=Game.GameType.HOME,
                date=dt.date(2025, 10, 1), time=dt.time(t, 0), court="1",
            )
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(20, 0),
        )
        result = get_gym_coverage(season)
        assert len(result["surplus"]) == 4
        expected = [
            ("09:00", "09:30", 30),
            ("11:45", "13:30", 105),
            ("15:45", "16:30", 45),
            ("18:45", "20:00", 75),
        ]
        for entry, (start, end, mins) in zip(result["surplus"], expected, strict=True):
            assert entry["start"] == start
            assert entry["end"] == end
            assert entry["minutes"] == mins

    def test_zero_margins_change_surplus_windows(self, season, home_game):
        config = SiteConfig.load()
        config.gym_margin_before_minutes = 0
        config.gym_margin_after_minutes = 0
        config.save()
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(20, 0),
        )
        result = get_gym_coverage(season)
        assert len(result["surplus"]) == 2
        assert result["surplus"][0]["start"] == "09:00"
        assert result["surplus"][0]["end"] == "14:00"
        assert result["surplus"][0]["minutes"] == 300
        assert result["surplus"][1]["start"] == "15:30"
        assert result["surplus"][1]["end"] == "20:00"
        assert result["surplus"][1]["minutes"] == 270

    def test_away_game_does_not_shrink_surplus(self, season, team):
        Game.objects.create(
            season=season, own_team=team, opponent="Quickpoint",
            game_type=Game.GameType.AWAY,
            date=dt.date(2025, 10, 1), time=dt.time(14, 0), court="1",
        )
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(17, 0),
        )
        result = get_gym_coverage(season)
        assert len(result["surplus"]) == 1
        assert result["surplus"][0]["minutes"] == 480
