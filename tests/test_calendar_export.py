"""Tests for calendar (.ics) export."""

import datetime as dt

import pytest

from hoops_planner.core.calendar_export import export_schedule_ics
from hoops_planner.core.models import (
    Game,
    Task,
    TaskAssignment,
    TaskType,
)


@pytest.mark.django_db
class TestExportScheduleIcs:
    def test_produces_valid_ics(self, season, team_x14, player):
        """Verify the .ics output is valid and contains game data."""
        game = Game.objects.create(
            season=season,
            home_team=team_x14,
            away_team="Achilles '71",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        scorer_task = Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        TaskAssignment.objects.create(task=scorer_task, player=player)

        ics_bytes = export_schedule_ics(season)
        ics_text = ics_bytes.decode("utf-8")

        # ICS structure
        assert "BEGIN:VCALENDAR" in ics_text
        assert "END:VCALENDAR" in ics_text
        assert "VERSION:2.0" in ics_text
        assert "BEGIN:VEVENT" in ics_text
        assert "END:VEVENT" in ics_text

        # Game data should be present
        assert "Vido X14-1" in ics_text
        assert "Achilles '71" in ics_text

        # Date/time in ICS format (YYYYMMDDTHHMMSS)
        assert "20251001T140000" in ics_text

        # Player assignment should appear in description
        assert "John Doe" in ics_text
        assert "Scorer" in ics_text

        # Location should mention the venue and court
        assert "Den Ekkerman" in ics_text
        assert "Court 1" in ics_text

    def test_empty_season(self, season):
        """An empty season should still produce a valid (empty) ICS file."""
        ics_bytes = export_schedule_ics(season)
        ics_text = ics_bytes.decode("utf-8")

        assert "BEGIN:VCALENDAR" in ics_text
        assert "END:VCALENDAR" in ics_text
        assert "BEGIN:VEVENT" not in ics_text

    def test_multiple_games(self, season, team_x14):
        """Multiple games should each produce a VEVENT."""
        Game.objects.create(
            season=season,
            home_team=team_x14,
            away_team="Opponent A",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        Game.objects.create(
            season=season,
            home_team=team_x14,
            away_team="Opponent B",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 2),
            time=dt.time(16, 0),
            court=Game.Court.COURT_2,
        )

        ics_bytes = export_schedule_ics(season)
        ics_text = ics_bytes.decode("utf-8")

        # Should have two VEVENTs
        assert ics_text.count("BEGIN:VEVENT") == 2
        assert ics_text.count("END:VEVENT") == 2

        # Both opponents should be present
        assert "Opponent A" in ics_text
        assert "Opponent B" in ics_text

    def test_custom_location_in_ics(self, season, team_x14, player):
        """Custom location should appear in the ICS output."""
        game = Game.objects.create(
            season=season,
            home_team=team_x14,
            away_team="Achilles '71",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
            location="De Kempencampus",
        )
        scorer_task = Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        TaskAssignment.objects.create(task=scorer_task, player=player)

        ics_bytes = export_schedule_ics(season)
        ics_text = ics_bytes.decode("utf-8")

        assert "De Kempencampus" in ics_text
        assert "Court 1" in ics_text
