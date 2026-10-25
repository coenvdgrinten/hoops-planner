"""Tests for PDF export."""

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
            own_team=team_x14,
            opponent="Achilles '71",
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
            own_team=team_x14,
            opponent="Opponent",
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

    def test_pdf_player_summary_eff_column(self, season, team_x14, player):
        """Player Summary includes an 'Eff.' column with weighted totals."""
        # Game on team_x14's date → own-team task counts 1×.
        game = Game.objects.create(
            season=season,
            own_team=team_x14,
            opponent="Opponent",
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

        # Away-day game (different team, different date) → counts 2×.
        other_team = Team.objects.create(
            name="Vido X16-1",
            age_category=Team.AgeCategory.X16,
        )
        away_game = Game.objects.create(
            season=season,
            own_team=other_team,
            opponent="Away Opp",
            game_type=Game.GameType.AWAY,
            date=dt.date(2025, 10, 8),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        timer_task = Task.objects.create(
            game=away_game,
            task_type=TaskType.TIMER,
            slot_number=1,
        )
        TaskAssignment.objects.create(task=timer_task, player=player)

        html = _build_html(season)
        # Header includes Eff.
        assert "<th>Eff.</th>" in html
        # John Doe: 1 own-day task (eff 1) + 1 away-day task (eff 2) = eff 3, total 2
        # The row should show both "2" (total) and "3" (eff)
        john_rows = [line for line in html.split("\n") if "John Doe" in line]
        assert any("<td>2</td><td>3</td>" in line for line in john_rows)

    def test_pdf_contains_team_summary(self, season, team_x14, player):
        """Verify the PDF HTML includes a per-team total task count."""
        game = Game.objects.create(
            season=season,
            own_team=team_x14,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        # Two tasks assigned to the same team's member → team total of 2.
        scorer_task = Task.objects.create(
            game=game, task_type=TaskType.SCORER, slot_number=1
        )
        timer_task = Task.objects.create(
            game=game, task_type=TaskType.TIMER, slot_number=1
        )
        TaskAssignment.objects.create(task=scorer_task, player=player)
        TaskAssignment.objects.create(task=timer_task, player=player)

        html = _build_html(season)

        # Team summary section should be present with the team name.
        assert "Team Summary" in html
        assert "Total Tasks" in html
        assert "Vido X14-1" in html

    def test_pdf_team_summary_absent_when_no_assignments(self, season, team_x14):
        """No team summary section when nothing has been assigned."""
        game = Game.objects.create(
            season=season,
            own_team=team_x14,
            opponent="Opponent",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
        )
        Task.objects.create(game=game, task_type=TaskType.SCORER, slot_number=1)

        html = _build_html(season)
        assert "Team Summary" not in html

    def test_pdf_contains_unassigned_indicator(self, season, team_x14):
        """Verify unassigned slots show a placeholder indicator."""
        game = Game.objects.create(
            season=season,
            own_team=team_x14,
            opponent="Opponent",
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
            own_team=team_x14,
            opponent="Opponent",
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
            own_team=team_x14,
            opponent="Opponent",
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
            own_team=team_x14,
            opponent="Opponent",
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

    def test_pdf_no_parent_label_for_coach_of_other_parent_team(self, season, team_x14):
        """A member of a non-parent team who COACHES a parent team must not be
        labelled 'Ouder van' for the non-parent team's scorer/timer slot."""
        # A kids team with parent_responsible that the player coaches.
        kid_team = Team.objects.create(
            name="Vido X12-2",
            age_category=Team.AgeCategory.X12,
            parent_responsible=True,
        )
        # The player belongs to an adult (non-parent) team.
        adult_team = Team.objects.create(
            name="Vido VSE1",
            age_category=Team.AgeCategory.VSE,
        )
        coach = Player.objects.create(
            first_name="Tessa",
            last_name="Kramer",
            team=adult_team,
        )
        coach.coached_teams.add(kid_team)

        # Task is on the ADULT team's game (not the kid team).
        game = Game.objects.create(
            season=season,
            own_team=adult_team,
            opponent="Opponent",
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
        TaskAssignment.objects.create(task=scorer_task, player=coach)

        html = _build_html(season)
        # Plain name, no "Ouder van" prefix.
        assert "Ouder van Tessa Kramer" not in html
        assert "Tessa Kramer" in html

    def test_pdf_away_day_multiplier(self, season, team_x14, player):
        """Away-day class when the player's team plays no game that date."""
        other_team = Team.objects.create(
            name="Vido X16-1",
            age_category=Team.AgeCategory.X16,
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
        scorer_task = Task.objects.create(
            game=game,
            task_type=TaskType.SCORER,
            slot_number=1,
        )
        TaskAssignment.objects.create(task=scorer_task, player=player)

        html = _build_html(season)
        # Player's team (team_x14) has no game on this date → away-day class
        assert 'class="center away-day"' in html
        assert 'class="team away-day"' in html

    def test_pdf_no_away_day_for_own_home_game(self, season, team_x14, player):
        """No away-day class when the player works on their own team's home game.

        Regression: the previous check excluded the current game from the
        "does my team play today" query, which wrongly flagged every member
        of the home team as away on their own home game.
        """
        game = Game.objects.create(
            season=season,
            own_team=team_x14,
            opponent="Opponent",
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
        # (The CSS rule .away-day is always present — check the td markup.)
        assert 'class="center away-day"' not in html
        assert 'class="team away-day"' not in html


@pytest.mark.django_db
class TestExportScope:
    """Half / custom game scoping of the exported document (issue #9)."""

    def _make_one_game_per_half(self, season, team_x14, player):
        """A half-1 and a half-2 game, each with an assigned scorer task."""
        g1 = Game.objects.create(
            season=season,
            own_team=team_x14,
            opponent="First Half Opp",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
            half=Game.Half.FIRST,
        )
        t1 = Task.objects.create(game=g1, task_type=TaskType.SCORER, slot_number=1)
        TaskAssignment.objects.create(task=t1, player=player)
        g2 = Game.objects.create(
            season=season,
            own_team=team_x14,
            opponent="Second Half Opp",
            game_type=Game.GameType.HOME,
            date=dt.date(2026, 1, 10),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
            half=Game.Half.SECOND,
        )
        t2 = Task.objects.create(game=g2, task_type=TaskType.SCORER, slot_number=1)
        TaskAssignment.objects.create(task=t2, player=player)
        return g1, g2

    def test_build_html_scoped_to_first_half(self, season, team_x14, player):
        self._make_one_game_per_half(season, team_x14, player)

        html = _build_html(season, half="1")
        assert "First Half Opp" in html
        assert "01-10-2025" in html
        assert "Second Half Opp" not in html
        assert "10-01-2026" not in html

    def test_build_html_scoped_to_second_half(self, season, team_x14, player):
        self._make_one_game_per_half(season, team_x14, player)

        html = _build_html(season, half="2")
        assert "Second Half Opp" in html
        assert "10-01-2026" in html
        assert "First Half Opp" not in html
        assert "01-10-2025" not in html

    def test_build_html_default_is_whole_season(self, season, team_x14, player):
        """No scope args → both halves rendered (backward-compatible default)."""
        self._make_one_game_per_half(season, team_x14, player)

        html = _build_html(season)
        assert "First Half Opp" in html
        assert "Second Half Opp" in html

    def test_build_html_custom_game_subset(self, season, team_x14, player):
        g1, _ = self._make_one_game_per_half(season, team_x14, player)
        g3 = Game.objects.create(
            season=season,
            own_team=team_x14,
            opponent="Third Game Opp",
            game_type=Game.GameType.HOME,
            date=dt.date(2026, 2, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
            half=Game.Half.SECOND,
        )
        Task.objects.create(game=g3, task_type=TaskType.SCORER, slot_number=1)

        html = _build_html(season, game_ids=[g1.id, g3.id])
        assert "First Half Opp" in html
        assert "Third Game Opp" in html
        assert "Second Half Opp" not in html

    def test_build_html_title_indicates_scope(self, season, team_x14, player):
        g1, _ = self._make_one_game_per_half(season, team_x14, player)

        assert "Task Schedule — 2025-2026 (First Half)" in _build_html(
            season, half="1"
        )
        assert "Task Schedule — 2025-2026 (Second Half)" in _build_html(
            season, half="2"
        )
        assert "Task Schedule — 2025-2026 (Custom Selection)" in _build_html(
            season, game_ids=[g1.id]
        )
        # Whole season: no parenthetical.
        whole = _build_html(season)
        assert "Task Schedule — 2025-2026</span>" in whole

    def test_team_summary_follows_scope(self, season, team_x14, player):
        """Scoped summary counts only the selected games' assignments."""
        g1, g2 = self._make_one_game_per_half(season, team_x14, player)
        # A second assignment in the first-half game → scoped total 2, full 3.
        extra_task = Task.objects.create(
            game=g1, task_type=TaskType.TIMER, slot_number=1
        )
        TaskAssignment.objects.create(task=extra_task, player=player)

        scoped = _build_html(season, half="1")
        unscoped = _build_html(season)

        # In the team summary row, Vido X14-1's total is the 2nd <td>.
        scoped_row = next(
            line
            for line in scoped.split("\n")
            if "Vido X14-1" in line and "<td>2</td>" in line
        )
        assert "<td>2</td>" in scoped_row
        unscoped_rows = [
            line
            for line in unscoped.split("\n")
            if "Vido X14-1" in line and "<td>3</td>" in line
        ]
        assert unscoped_rows

    def test_player_summary_eff_identical_across_scopes(
        self, season, team_x14, player
    ):
        """Eff. figures are identical whether or not the scope filter is
        applied (the 2× multiplier depends only on same-date games)."""
        # Own-team-date game in half 1 → eff 1.
        g1 = Game.objects.create(
            season=season,
            own_team=team_x14,
            opponent="Own Day Opp",
            game_type=Game.GameType.HOME,
            date=dt.date(2025, 10, 1),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
            half=Game.Half.FIRST,
        )
        t1 = Task.objects.create(game=g1, task_type=TaskType.SCORER, slot_number=1)
        TaskAssignment.objects.create(task=t1, player=player)
        # Away-day game in half 2 (other team, other date) → eff 2.
        other_team = Team.objects.create(
            name="Vido X16-1", age_category=Team.AgeCategory.X16
        )
        g2 = Game.objects.create(
            season=season,
            own_team=other_team,
            opponent="Away Day Opp",
            game_type=Game.GameType.AWAY,
            date=dt.date(2026, 1, 10),
            time=dt.time(14, 0),
            court=Game.Court.COURT_1,
            half=Game.Half.SECOND,
        )
        t2 = Task.objects.create(game=g2, task_type=TaskType.TIMER, slot_number=1)
        TaskAssignment.objects.create(task=t2, player=player)

        def john_row(html):
            # The player-summary row (the game-table row also mentions the
            # player, but its cells never match the Total/Eff. pattern).
            return next(
                line for line in html.split("\n") if "<td>John Doe</td>" in line
            )

        # Half 1 only: 1 task, eff 1.
        h1 = _build_html(season, half="1")
        assert "<td>1</td><td>1</td>" in john_row(h1)
        assert "Away Day Opp" not in h1
        # Half 2 only: 1 task, eff 2 — same multiplier as in the full run.
        h2 = _build_html(season, half="2")
        assert "<td>1</td><td>2</td>" in john_row(h2)
        # Whole season: 2 tasks, eff 3.
        whole = _build_html(season)
        assert "<td>2</td><td>3</td>" in john_row(whole)

    def test_full_season_stats_opts_into_season_wide_summaries(
        self, season, team_x14, player
    ):
        """full_season_stats=True: tables stay scoped, summaries go wide."""
        self._make_one_game_per_half(season, team_x14, player)

        html = _build_html(season, half="1", full_season_stats=True)
        # Tables still scoped to the first half…
        assert "First Half Opp" in html
        assert "Second Half Opp" not in html
        # …but the team summary counts both halves (2 assignments total).
        team_rows = [
            line
            for line in html.split("\n")
            if "Vido X14-1" in line and "<td>2</td>" in line
        ]
        assert team_rows
        # John Doe's player-summary total spans both halves.
        john_rows = [line for line in html.split("\n") if "John Doe" in line]
        assert any("<td>2</td><td>2</td>" in line for line in john_rows)

    def test_summaries_absent_when_no_assignments_in_scope(
        self, season, team_x14, player
    ):
        """A scope without assignments yields no summary sections and no
        trailing page break."""
        g1, g2 = self._make_one_game_per_half(season, team_x14, player)
        # Move all assignments out of half 1: reassign them to half 2 only.
        TaskAssignment.objects.filter(task__game=g1).delete()

        html = _build_html(season, half="1")
        assert "Team Summary" not in html
        assert "Player Summary" not in html
        assert "page-break-before" not in html
        # The schedule table for the (unassigned) first-half game is present.
        assert "First Half Opp" in html
