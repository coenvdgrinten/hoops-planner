"""Tests for CSV import logic."""

import pytest

from sixth_man.core.importers import import_members, import_schedule
from sixth_man.core.models import (
    Game,
    Player,
    Season,
    Task,
    Team,
)

SCHEDULE_CSV = """date,time,court,home_team,away_team
2025-10-01,14:00,1,Vido X14-1,Achilles '71
2025-10-01,14:00,2,Vido X10-1,Jumping Giants
2025-10-01,16:00,1,Vido X14-1,Attacus
"""

MEMBERS_CSV = """first_name,last_name,team,is_coach,referee_certification
John,Doe,Vido X14-1,False,T1
Jane,Smith,Vido X14-1,True,NONE
Coach,Karlos,Vido X14-1,True,T2
Peter,Jones,Vido X10-1,False,NONE
"""


@pytest.mark.django_db
class TestImportSchedule:
    def test_creates_season(self):
        import_schedule(SCHEDULE_CSV, "2025-2026")
        assert Season.objects.filter(name="2025-2026").exists()

    def test_creates_games(self):
        result = import_schedule(SCHEDULE_CSV, "2025-2026")
        assert result["games"] == 3
        assert Game.objects.count() == 3

    def test_creates_teams(self):
        import_schedule(SCHEDULE_CSV, "2025-2026")
        assert Team.objects.filter(name="Vido X14-1").exists()
        assert Team.objects.filter(name="Vido X10-1").exists()

    def test_infers_age_category(self):
        import_schedule(SCHEDULE_CSV, "2025-2026")
        team = Team.objects.get(name="Vido X14-1")
        assert team.age_category == Team.AgeCategory.X14
        team10 = Team.objects.get(name="Vido X10-1")
        assert team10.age_category == Team.AgeCategory.X10

    def test_creates_task_slots(self):
        result = import_schedule(SCHEDULE_CSV, "2025-2026")
        # 3 games, each needs scorer + timer + 2 referees = 5 tasks
        assert result["tasks"] >= 3  # at least scorer, timer, referees
        game = Game.objects.first()
        tasks = Task.objects.filter(game=game)
        task_types = tasks.values_list("task_type", "slot_number")
        assert ("SCORER", 1) in list(task_types)
        assert ("TIMER", 1) in list(task_types)

    def test_idempotent_same_schedule(self):
        import_schedule(SCHEDULE_CSV, "2025-2026")
        result = import_schedule(SCHEDULE_CSV, "2025-2026")
        # No new games created on second import
        assert result["games"] == 0
        assert Game.objects.count() == 3


@pytest.mark.django_db
class TestImportMembers:
    def test_creates_players(self):
        result = import_members(MEMBERS_CSV)
        assert result["players_created"] == 4

    def test_creates_teams(self):
        result = import_members(MEMBERS_CSV)
        assert result["teams"] == 2

    def test_parses_coach_flag(self):
        import_members(MEMBERS_CSV)
        coach = Player.objects.get(first_name="Jane", last_name="Smith")
        assert coach.is_coach is True
        player = Player.objects.get(first_name="John", last_name="Doe")
        assert player.is_coach is False

    def test_parses_certification(self):
        import_members(MEMBERS_CSV)
        player = Player.objects.get(first_name="John", last_name="Doe")
        assert player.referee_certification == Player.RefereeCertification.T1

    def test_upsert_updates_existing(self):
        # First import
        import_members(MEMBERS_CSV)
        # Second import — all should be updates
        result = import_members(MEMBERS_CSV)
        assert result["players_created"] == 0
        assert result["players_updated"] == 4
