"""Tests for PDF export."""

import datetime as dt

import pytest

from hoops_planner.core.models import (
    Game,
    Task,
    TaskAssignment,
    TaskType,
    Team,
)
from hoops_planner.core.pdf_export import _build_html, export_schedule_pdf


@pytest.mark.django_db
class TestExportSchedulePdf:
    def test_produces_pdf_bytes(self, season):
        team = Team.objects.create(
            name="Vido X14-1",
            age_category=Team.AgeCategory.X14,
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
        Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )

        pdf_bytes = export_schedule_pdf(season)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        # PDF files start with %PDF
        assert pdf_bytes[:4] == b"%PDF"

    def test_empty_season(self, season):
        pdf_bytes = export_schedule_pdf(season)
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes[:4] == b"%PDF"

    def test_pdf_contains_schedule_content(self, season, team_x14, player):
        """Verify the PDF HTML includes game data: team names, dates, task types."""
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

        html = _build_html(season)

        # Team names should appear in the HTML
        assert "Vido X14-1" in html
        assert "Achilles '71" in html

        # Date should appear (formatted as DD-MM-YYYY)
        assert "01-10-2025" in html

        # Task type labels should appear
        assert "Scorer" in html

        # Player name should appear (assigned scorer)
        assert "John Doe" in html

        # Season name should appear
        assert "2025-2026" in html

    def test_pdf_contains_player_summary(self, season, team_x14, player):
        """Verify the PDF HTML includes a player summary section."""
        game = Game.objects.create(
            season=season,
            home_team=team_x14,
            away_team="Opponent",
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

        html = _build_html(season)

        # Player summary section should be present
        assert "Player Summary" in html
        assert "John Doe" in html

    def test_pdf_contains_unassigned_indicator(self, season, team_x14):
        """Verify unassigned slots show a placeholder indicator."""
        game = Game.objects.create(
            season=season,
            home_team=team_x14,
            away_team="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        Task.objects.create(game=game, task_type=TaskType.REFEREE, slot_number=1)
        Task.objects.create(game=game, task_type=TaskType.SCORER, slot_number=1)
        Task.objects.create(game=game, task_type=TaskType.TIMER, slot_number=1)

        html = _build_html(season)

        # Unassigned slots should show the placeholder
        assert "unassigned" in html

    def test_pdf_contains_24_second_operator(self, season, team_x14, player):
        """Verify 24-second operator column appears when a team requires it."""
        team_x14.requires_24_second_operator = True
        team_x14.save()
        game = Game.objects.create(
            season=season,
            home_team=team_x14,
            away_team="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        Task.objects.create(
            game=game,
            task_type=TaskType.SECOND_24_OPERATOR,
            slot_number=1,
        )

        html = _build_html(season)
        assert "24 sec" in html

    def test_pdf_multiple_referees(self, season, team_x14, player):
        """Verify multiple referee columns appear."""
        game = Game.objects.create(
            season=season,
            home_team=team_x14,
            away_team="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        Task.objects.create(game=game, task_type=TaskType.REFEREE, slot_number=1)
        Task.objects.create(game=game, task_type=TaskType.REFEREE, slot_number=2)

        html = _build_html(season)
        # Two referee columns should be present
        assert "Scheidsr" in html
        assert "Scheidsr #2" in html

    def test_pdf_parent_responsible_label(self, season, team_x14, player):
        """Verify parent_responsible players get 'Ouder van' label."""
        team_x14.parent_responsible = True
        team_x14.save()
        game = Game.objects.create(
            season=season,
            home_team=team_x14,
            away_team="Opponent",
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

        html = _build_html(season)
        assert "Ouder van John Doe" in html

    def test_pdf_away_day_multiplier(self, season, team_x14, player):
        """Verify away-day class is applied when player's team has no game."""
        game = Game.objects.create(
            season=season,
            home_team=team_x14,
            away_team="Opponent",
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

        html = _build_html(season)
        # Player's team has no game on this date → away-day class
        assert "away-day" in html
