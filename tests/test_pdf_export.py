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
