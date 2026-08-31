"""Tests for find_conflicts_for_game — per-game conflict detection.

This is the seam used by the ``tasks_with_assignments`` endpoint to flag
assignments that became invalid after roster/schedule changes. It must report
the same reasons (and priority order) as ``find_conflicting_assignments``,
scoped to one game.
"""

import datetime as dt

import pytest

from hoops_planner.core.eligibility import (
    find_conflicting_assignments,
    find_conflicts_for_game,
)
from hoops_planner.core.models import (
    Game,
    Player,
    Task,
    TaskAssignment,
    TaskType,
    Team,
)


def make_team(name: str, category: str, **kwargs):
    return Team.objects.create(name=name, age_category=category, **kwargs)


def make_player(team, first: str = "P", last: str = "L", **kwargs):
    return Player.objects.create(
        first_name=first, last_name=last, team=team, **kwargs
    )


def make_game(season, own_team: Team, **kwargs) -> Game:
    defaults = {
        "opponent": "Opponent",
        "game_type": Game.GameType.HOME,
        "date": dt.date(2025, 10, 1),
        "time": dt.time(14, 0),
        "court": Game.Court.COURT_1,
    }
    defaults.update(kwargs)
    return Game.objects.create(season=season, own_team=own_team, **defaults)


@pytest.mark.django_db
class TestFindConflictsForGame:
    """Each mutation scenario that can invalidate an existing assignment."""

    def test_valid_assignment_has_no_conflict(self, season):
        """A fully valid assignment yields an empty mapping."""
        team_a = make_team("Vido X14-1", Team.AgeCategory.X14)
        team_b = make_team("Vido X10-1", Team.AgeCategory.X10)
        player = make_player(team_a, referee_certification="F")
        game = make_game(season, team_b)
        task = Task.objects.create(game=game, task_type=TaskType.REFEREE)
        TaskAssignment.objects.create(player=player, task=task)

        assert find_conflicts_for_game(game) == {}

    def test_player_moved_to_own_team_of_game(self, season):
        """Member changed team to the game's own team → conflict."""
        team_a = make_team("Vido X14-1", Team.AgeCategory.X14)
        team_b = make_team("Vido X10-1", Team.AgeCategory.X10)
        player = make_player(team_a, referee_certification="F")
        game = make_game(season, team_b)
        task = Task.objects.create(game=game, task_type=TaskType.REFEREE)
        assignment = TaskAssignment.objects.create(player=player, task=task)

        assert find_conflicts_for_game(game) == {}

        # Roster change: the member joins the team playing in this game.
        player.team = team_b
        player.save(update_fields=["team"])

        result = find_conflicts_for_game(game)
        assert result == {assignment.id: "Cannot be assigned to own team's game"}

    def test_player_coaches_own_team_of_game(self, season):
        """Member now coaches the game's own team → conflict."""
        team_a = make_team("Vido X14-1", Team.AgeCategory.X14)
        team_b = make_team("Vido X10-1", Team.AgeCategory.X10)
        player = make_player(team_a, referee_certification="F")
        game = make_game(season, team_b)
        task = Task.objects.create(game=game, task_type=TaskType.SCORER)
        assignment = TaskAssignment.objects.create(player=player, task=task)

        assert find_conflicts_for_game(game) == {}

        player.coached_teams.add(team_b)

        result = find_conflicts_for_game(game)
        assert result == {assignment.id: "Cannot be assigned to own team's game"}

    def test_parent_responsible_exception_still_holds(self, season):
        """SCORER/TIMER on a parent_responsible team is NOT a conflict.

        Mirrors the eligibility rule: parents fill scorer/timer for their
        kid's team, so a member of such a team may stay assigned.
        """
        team_a = make_team("Vido X14-1", Team.AgeCategory.X14)
        team_b = make_team(
            "Vido X10-2", Team.AgeCategory.X10, parent_responsible=True
        )
        player = make_player(team_a)
        game = make_game(season, team_b)
        task = Task.objects.create(game=game, task_type=TaskType.SCORER)
        TaskAssignment.objects.create(player=player, task=task)

        # Player moves onto the parent-responsible team: still fine for SCORER.
        player.team = team_b
        player.save(update_fields=["team"])

        assert find_conflicts_for_game(game) == {}

    def test_away_game_added_same_day(self, season):
        """Away game for the player's team on the same day → conflict."""
        team_a = make_team("Vido X14-1", Team.AgeCategory.X14)
        team_b = make_team("Vido X10-1", Team.AgeCategory.X10)
        player = make_player(team_a, referee_certification="F")
        game = make_game(season, team_b)
        task = Task.objects.create(game=game, task_type=TaskType.REFEREE)
        assignment = TaskAssignment.objects.create(player=player, task=task)

        assert find_conflicts_for_game(game) == {}

        make_game(
            season,
            team_a,
            opponent="Away Opp",
            game_type=Game.GameType.AWAY,
            time=dt.time(10, 0),
        )

        result = find_conflicts_for_game(game)
        assert result == {
            assignment.id: "Team has an away game on the same day"
        }

    def test_home_game_added_same_time(self, season):
        """Home game for the player's team at the same time → conflict."""
        team_a = make_team("Vido X14-1", Team.AgeCategory.X14)
        team_c = make_team("Vido X12-1", Team.AgeCategory.X12)
        player = make_player(team_a)
        game = make_game(season, team_c)
        task = Task.objects.create(game=game, task_type=TaskType.SCORER)
        assignment = TaskAssignment.objects.create(player=player, task=task)

        assert find_conflicts_for_game(game) == {}

        make_game(season, team_a, opponent="Home Opp", court=Game.Court.COURT_2)

        result = find_conflicts_for_game(game)
        assert result == {assignment.id: "Team has a home game at the same time"}

    def test_double_booking_at_same_time(self, season):
        """Another assignment at the same date/time → conflict.

        Can arise via write paths that bypass serializer validation.
        """
        team_a = make_team("Vido X14-1", Team.AgeCategory.X14)
        team_b = make_team("Vido X10-1", Team.AgeCategory.X10)
        team_c = make_team("Vido X12-1", Team.AgeCategory.X12)
        player = make_player(team_a)
        game = make_game(season, team_b)
        task = Task.objects.create(game=game, task_type=TaskType.SCORER)
        assignment = TaskAssignment.objects.create(player=player, task=task)

        assert find_conflicts_for_game(game) == {}

        # Second game in the same time slot (other court), player force-assigned.
        game2 = make_game(season, team_c, court=Game.Court.COURT_2)
        task2 = Task.objects.create(game=game2, task_type=TaskType.TIMER)
        TaskAssignment.objects.create(player=player, task=task2)

        result = find_conflicts_for_game(game)
        assert result == {
            assignment.id: "Already assigned to another task at this time"
        }
        # The reverse direction is reported too.
        result2 = find_conflicts_for_game(game2)
        assert list(result2.values()) == [
            "Already assigned to another task at this time"
        ]

    def test_player_marked_exempt_after_assignment(self, season):
        """Exemption set after assignment → conflict."""
        team_a = make_team("Vido X14-1", Team.AgeCategory.X14)
        team_b = make_team("Vido X10-1", Team.AgeCategory.X10)
        player = make_player(team_a)
        game = make_game(season, team_b)
        task = Task.objects.create(game=game, task_type=TaskType.SCORER)
        assignment = TaskAssignment.objects.create(player=player, task=task)

        assert find_conflicts_for_game(game) == {}

        player.is_exempt = True
        player.save(update_fields=["is_exempt"])

        result = find_conflicts_for_game(game)
        assert result == {assignment.id: "Exempt from task assignments"}

    def test_referee_age_rule_after_team_change(self, season):
        """Player's highest team drops below the game's category → conflict."""
        team_vse1 = make_team("Vido VSE1", Team.AgeCategory.VSE)
        team_vse2 = make_team("Vido VSE2", Team.AgeCategory.VSE)
        team_x10 = make_team("Vido X10-1", Team.AgeCategory.X10)
        player = make_player(team_vse2, referee_certification="F")
        game = make_game(season, team_vse1)
        task = Task.objects.create(game=game, task_type=TaskType.REFEREE)
        assignment = TaskAssignment.objects.create(player=player, task=task)

        # Adult (VSE) members may referee any game.
        assert find_conflicts_for_game(game) == {}

        # Roster change: player moves down to X10.
        player.team = team_x10
        player.save(update_fields=["team"])

        result = find_conflicts_for_game(game)
        assert result == {
            assignment.id: "Player's team is younger than game team"
        }

    def test_referee_certification_lost(self, season):
        """Certification downgraded to NONE after assignment → conflict."""
        team_a = make_team("Vido X14-1", Team.AgeCategory.X14)
        team_b = make_team("Vido X10-1", Team.AgeCategory.X10)
        player = make_player(team_a, referee_certification="F")
        game = make_game(season, team_b)
        task = Task.objects.create(game=game, task_type=TaskType.REFEREE)
        assignment = TaskAssignment.objects.create(player=player, task=task)

        assert find_conflicts_for_game(game) == {}

        player.referee_certification = Player.RefereeCertification.NONE
        player.save(update_fields=["referee_certification"])

        result = find_conflicts_for_game(game)
        assert result == {
            assignment.id: "Missing required referee certification"
        }

    def test_scoring_task_not_subject_to_referee_rules(self, season):
        """Non-referee tasks ignore age and certification rules."""
        team_a = make_team("Vido X10-1", Team.AgeCategory.X10)
        team_vse = make_team("Vido VSE1", Team.AgeCategory.VSE)
        player = make_player(team_a)  # no certification, youngest category
        game = make_game(season, team_vse)
        task = Task.objects.create(game=game, task_type=TaskType.SCORER)
        TaskAssignment.objects.create(player=player, task=task)

        assert find_conflicts_for_game(game) == {}

    def test_only_reports_assignments_of_the_given_game(self, season):
        """Conflicts on other games are out of scope."""
        team_a = make_team("Vido X14-1", Team.AgeCategory.X14)
        team_b = make_team("Vido X10-1", Team.AgeCategory.X10)
        team_c = make_team("Vido X12-1", Team.AgeCategory.X12)
        player = make_player(team_a)
        game = make_game(season, team_b)
        other_game = make_game(season, team_c, court=Game.Court.COURT_2)
        task = Task.objects.create(game=game, task_type=TaskType.SCORER)
        other_task = Task.objects.create(game=other_game, task_type=TaskType.TIMER)
        TaskAssignment.objects.create(player=player, task=task)
        TaskAssignment.objects.create(player=player, task=other_task)

        # Away game for the player's team: both assignments conflict globally,
        # but only the one on `game` is reported here.
        make_game(
            season,
            team_a,
            opponent="Away Opp",
            game_type=Game.GameType.AWAY,
            time=dt.time(10, 0),
        )

        result = find_conflicts_for_game(game)
        assert len(result) == 1
        expected = "Team has an away game on the same day"
        assert all(v == expected for v in result.values())

    def test_reason_priority_when_several_rules_fire(self, season):
        """When several rules fire, the FIRST rule in the disqualification
        order wins (exemption beats schedule rules beat double-booking)."""
        team_a = make_team("Vido X14-1", Team.AgeCategory.X14)
        team_b = make_team("Vido X10-1", Team.AgeCategory.X10)
        team_c = make_team("Vido X12-1", Team.AgeCategory.X12)
        player = make_player(team_a, referee_certification="NONE")
        game = make_game(season, team_b)
        ref_task = Task.objects.create(game=game, task_type=TaskType.REFEREE)
        assignment = TaskAssignment.objects.create(player=player, task=ref_task)

        # Fire several rules at once: away game same day + double booking at
        # the same time + missing certification.
        make_game(
            season,
            team_a,
            opponent="Away Opp",
            game_type=Game.GameType.AWAY,
            time=dt.time(10, 0),
        )
        game2 = make_game(season, team_c, court=Game.Court.COURT_2)
        task2 = Task.objects.create(game=game2, task_type=TaskType.TIMER)
        TaskAssignment.objects.create(player=player, task=task2)

        # Away-day rule outranks double-booking and certification.
        result = find_conflicts_for_game(game)
        assert result[assignment.id] == "Team has an away game on the same day"

        # Exemption outranks everything.
        player.is_exempt = True
        player.save(update_fields=["is_exempt"])
        result = find_conflicts_for_game(game)
        assert result[assignment.id] == "Exempt from task assignments"

    def test_per_game_and_season_wide_report_same_reason(self, season):
        """The per-game helper and the season-wide detector agree."""
        team_a = make_team("Vido X14-1", Team.AgeCategory.X14)
        team_b = make_team("Vido X10-1", Team.AgeCategory.X10)
        player = make_player(team_a)
        game = make_game(season, team_b)
        task = Task.objects.create(game=game, task_type=TaskType.SCORER)
        assignment = TaskAssignment.objects.create(player=player, task=task)

        make_game(
            season,
            team_a,
            opponent="Away Opp",
            game_type=Game.GameType.AWAY,
            time=dt.time(10, 0),
        )

        global_conflicts = find_conflicting_assignments(season=season)
        global_reason = next(
            c["reason"] for c in global_conflicts if c["assignment"] == assignment
        )
        per_game = find_conflicts_for_game(game)
        assert per_game[assignment.id] == global_reason
