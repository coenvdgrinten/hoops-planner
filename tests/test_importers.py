"""Tests for CSV import logic."""

import pytest

from hoops_planner.core.importers import import_members, import_schedule
from hoops_planner.core.models import (
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
John,Doe,Vido X14-1,False,F
Jane,Smith,Vido X14-1,True,NONE
Coach,Karlos,Vido X14-1,True,SENIOR
Peter,Jones,Vido X10-1,False,NONE
"""


@pytest.mark.django_db
class TestImportSchedule:
    def test_creates_season(self):
        import_schedule(SCHEDULE_CSV, "2025-2026")
        assert Season.objects.filter(name="2025-2026").exists()

    def test_creates_games(self):
        result = import_schedule(SCHEDULE_CSV, "2025-2026")
        assert result["games_created"] == 3
        assert result["games_updated"] == 0
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

    def test_infers_vse_with_trailing_digit(self):
        """Team names like 'Vido VSE1' should infer VSE category."""
        csv_text = (
            "date,time,court,home_team,away_team\n"
            "2025-10-01,14:00,1,Vido VSE1,Opponent\n"
        )
        import_schedule(csv_text, "2025-2026")
        team = Team.objects.get(name="Vido VSE1")
        assert team.age_category == Team.AgeCategory.VSE

    def test_infers_mse_with_trailing_digit(self):
        """Team names like 'Vido MSE1' should infer MSE category."""
        csv_text = (
            "date,time,court,home_team,away_team\n"
            "2025-10-01,14:00,1,Vido MSE1,Opponent\n"
        )
        import_schedule(csv_text, "2025-2026")
        team = Team.objects.get(name="Vido MSE1")
        assert team.age_category == Team.AgeCategory.MSE

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
        # Second import in smart mode: matches existing games, no new creates
        assert result["games_created"] == 0
        assert result["games_updated"] == 0
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
        assert player.referee_certification == Player.RefereeCertification.F

    def test_upsert_updates_existing(self):
        # First import
        import_members(MEMBERS_CSV)
        # Second import — all should be updates
        result = import_members(MEMBERS_CSV)
        assert result["players_created"] == 0
        assert result["players_updated"] == 4


@pytest.mark.django_db
class TestImportScheduleGameType:
    def test_defaults_to_home(self):
        import_schedule(SCHEDULE_CSV, "2025-2026")
        assert Game.objects.filter(game_type=Game.GameType.HOME).count() == 3
        assert Game.objects.filter(game_type=Game.GameType.AWAY).count() == 0

    def test_honors_away_column(self):
        csv_text = (
            "date,time,court,home_team,away_team,game_type\n"
            "2025-10-01,14:00,1,Vido X14-1,Achilles '71,AWAY\n"
            "2025-10-01,16:00,1,Vido X10-1,Jumping Giants,HOME\n"
        )
        import_schedule(csv_text, "2025-2026")
        away = Game.objects.get(opponent="Achilles '71")
        assert away.game_type == Game.GameType.AWAY
        home = Game.objects.get(opponent="Jumping Giants")
        assert home.game_type == Game.GameType.HOME

    def test_case_insensitive_game_type(self):
        csv_text = (
            "date,time,court,home_team,away_team,game_type\n"
            "2025-10-01,14:00,1,Vido X14-1,Achilles '71,away\n"
        )
        import_schedule(csv_text, "2025-2026")
        assert (
            Game.objects.get(opponent="Achilles '71").game_type == Game.GameType.AWAY
        )

    def test_mixed_rows_with_and_without_game_type(self):
        """Rows shorter than the header must not crash (DictReader pads None)."""
        csv_text = (
            "date,time,court,home_team,away_team,game_type\n"
            "2025-10-01,14:00,1,Vido X14-1,Achilles '71\n"
            "2025-10-02,16:00,1,Vido X10-1,Jumping Giants,AWAY\n"
        )
        import_schedule(csv_text, "2025-2026")
        assert (
            Game.objects.get(opponent="Achilles '71").game_type == Game.GameType.HOME
        )
        assert (
            Game.objects.get(opponent="Jumping Giants").game_type == Game.GameType.AWAY
        )


@pytest.mark.django_db
class TestImportScheduleLocation:
    def test_defaults_to_den_ekkerman(self):
        """Games without a location column should default to Den Ekkerman."""
        import_schedule(SCHEDULE_CSV, "2025-2026")
        for game in Game.objects.all():
            assert game.location == "Den Ekkerman"

    def test_imports_location_from_csv(self):
        """Games with a location column should use the provided value."""
        csv_text = (
            "date,time,court,home_team,away_team,location\n"
            "2025-10-01,14:00,1,Vido X14-1,Achilles '71,Den Ekkerman\n"
            "2025-10-01,16:00,2,Vido X10-1,Jumping Giants,De Kempencampus\n"
        )
        import_schedule(csv_text, "2025-2026")
        game1 = Game.objects.get(opponent="Achilles '71")
        game2 = Game.objects.get(opponent="Jumping Giants")
        assert game1.location == "Den Ekkerman"
        assert game2.location == "De Kempencampus"

    def test_updates_location_on_smart_import(self):
        """Re-importing with a new location should update existing games."""
        import_schedule(SCHEDULE_CSV, "2025-2026")
        game = Game.objects.get(opponent="Achilles '71")
        assert game.location == "Den Ekkerman"

        csv_text = (
            "date,time,court,home_team,away_team,location\n"
            "2025-10-01,14:00,1,Vido X14-1,Achilles '71,De Kempencampus\n"
            "2025-10-01,14:00,2,Vido X10-1,Jumping Giants\n"
            "2025-10-01,16:00,1,Vido X14-1,Attacus\n"
        )
        import_schedule(csv_text, "2025-2026")
        game.refresh_from_db()
        assert game.location == "De Kempencampus"

    def test_invalid_game_type_defaults_to_home(self):
        csv_text = (
            "date,time,court,home_team,away_team,game_type\n"
            "2025-10-01,14:00,1,Vido X14-1,Achilles '71,NEUTRAL\n"
        )
        import_schedule(csv_text, "2025-2026")
        assert (
            Game.objects.get(opponent="Achilles '71").game_type == Game.GameType.HOME
        )

    def test_smart_update_changes_game_type(self):
        csv_text = (
            "date,time,court,home_team,away_team,game_type\n"
            "2025-10-01,14:00,1,Vido X14-1,Achilles '71,HOME\n"
        )
        import_schedule(csv_text, "2025-2026")
        game = Game.objects.get(opponent="Achilles '71")
        assert game.game_type == Game.GameType.HOME

        # Re-import the same fixture as an away game — should update, not duplicate
        csv_text_away = (
            "date,time,court,home_team,away_team,game_type\n"
            "2025-10-01,14:00,1,Vido X14-1,Achilles '71,AWAY\n"
        )
        result = import_schedule(csv_text_away, "2025-2026")
        assert result["games_created"] == 0
        assert result["games_updated"] == 1
        assert Game.objects.count() == 1
        assert (
            Game.objects.get(opponent="Achilles '71").game_type == Game.GameType.AWAY
        )

    def test_away_and_home_same_teams_distinct(self):
        """An away and a home fixture with the same teams/date are distinct rows."""
        csv_text = (
            "date,time,court,home_team,away_team,game_type\n"
            "2025-10-01,14:00,1,Vido X14-1,Achilles '71,HOME\n"
            "2025-10-01,14:00,2,Vido X14-1,Achilles '71,AWAY\n"
        )
        import_schedule(csv_text, "2025-2026")
        assert Game.objects.count() == 2


@pytest.mark.django_db
class TestTaskSlotStaffing:
    def test_defaults_create_scorer_timer_two_refs(self):
        csv_text = (
            "date,time,court,home_team,away_team\n"
            "2025-10-01,14:00,1,Vido X14-1,Achilles '71\n"
        )
        import_schedule(csv_text, "2025-2026")
        game = Game.objects.get()
        task_types = set(
            Task.objects.filter(game=game).values_list("task_type", "slot_number")
        )
        assert ("SCORER", 1) in task_types
        assert ("TIMER", 1) in task_types
        assert ("REFEREE", 1) in task_types
        assert ("REFEREE", 2) in task_types
        assert ("24_SECOND_OPERATOR", 1) not in task_types

    def test_settings_drive_referee_count(self):
        Team.objects.create(name="Vido X14-1", age_category="X14")
        Team.objects.filter(name="Vido X14-1").update(required_referees=3)
        csv_text = (
            "date,time,court,home_team,away_team\n"
            "2025-10-01,14:00,1,Vido X14-1,Achilles '71\n"
        )
        import_schedule(csv_text, "2025-2026")
        game = Game.objects.get()
        ref_slots = Task.objects.filter(game=game, task_type="REFEREE").count()
        assert ref_slots == 3

    def test_settings_enable_24_second_operator(self):
        Team.objects.create(name="Vido X14-1", age_category="X14")
        Team.objects.filter(name="Vido X14-1").update(requires_24_second_operator=True)
        csv_text = (
            "date,time,court,home_team,away_team\n"
            "2025-10-01,14:00,1,Vido X14-1,Achilles '71\n"
        )
        import_schedule(csv_text, "2025-2026")
        game = Game.objects.get()
        assert Task.objects.filter(game=game, task_type="24_SECOND_OPERATOR").exists()

    def test_settings_disable_scorer(self):
        Team.objects.create(name="Vido X14-1", age_category="X14")
        Team.objects.filter(name="Vido X14-1").update(require_scorer=False)
        csv_text = (
            "date,time,court,home_team,away_team\n"
            "2025-10-01,14:00,1,Vido X14-1,Achilles '71\n"
        )
        import_schedule(csv_text, "2025-2026")
        game = Game.objects.get()
        assert not Task.objects.filter(game=game, task_type="SCORER").exists()

    def test_optional_referees_create_marked_optional_slots(self):
        Team.objects.create(name="Vido X14-1", age_category="X14")
        Team.objects.filter(name="Vido X14-1").update(
            required_referees=1, optional_referees=1
        )
        csv_text = (
            "date,time,court,home_team,away_team\n"
            "2025-10-01,14:00,1,Vido X14-1,Achilles '71\n"
        )
        import_schedule(csv_text, "2025-2026")
        game = Game.objects.get()
        refs = Task.objects.filter(game=game, task_type="REFEREE").order_by(
            "slot_number"
        )
        assert refs.count() == 2
        assert refs[0].slot_number == 1 and refs[0].optional is False
        assert refs[1].slot_number == 2 and refs[1].optional is True


@pytest.mark.django_db
class TestImportScheduleReplace:
    def test_replace_deletes_existing_games(self):
        """replace=True should delete existing games before importing."""
        import_schedule(SCHEDULE_CSV, "2025-2026")
        assert Game.objects.count() == 3

        # Re-import with replace=True
        result = import_schedule(SCHEDULE_CSV, "2025-2026", replace=True)
        assert result["games_created"] == 3
        assert Game.objects.count() == 3

    def test_replace_removes_old_games(self):
        """replace=True should remove games not in the new CSV."""
        import_schedule(SCHEDULE_CSV, "2025-2026")
        assert Game.objects.count() == 3

        # Import a smaller schedule with replace=True
        smaller_csv = (
            "date,time,court,home_team,away_team\n"
            "2025-10-01,14:00,1,Vido X14-1,Achilles '71\n"
        )
        result = import_schedule(smaller_csv, "2025-2026", replace=True)
        assert result["games_created"] == 1
        assert Game.objects.count() == 1


@pytest.mark.django_db
class TestImportMembersExtended:
    def test_parses_is_exempt(self):
        csv_text = (
            "first_name,last_name,team,is_coach,is_exempt,referee_certification\n"
            "Board,Member,Vido X14-1,False,True,NONE\n"
        )
        import_members(csv_text)
        player = Player.objects.get(first_name="Board")
        assert player.is_exempt is True

    def test_parses_coached_teams(self):
        csv_text = (
            "first_name,last_name,team,is_coach,coached_teams,referee_certification\n"
            'Coach,Karlos,Vido X14-1,True,"Vido X10-1,Vido X12-1",NONE\n'
        )
        import_members(csv_text)
        player = Player.objects.get(first_name="Coach")
        coached = {t.name for t in player.coached_teams.all()}
        assert "Vido X10-1" in coached
        assert "Vido X12-1" in coached

    def test_invalid_certification_defaults_to_none(self):
        csv_text = (
            "first_name,last_name,team,is_coach,referee_certification\n"
            "John,Doe,Vido X14-1,False,INVALID\n"
        )
        import_members(csv_text)
        player = Player.objects.get(first_name="John")
        assert player.referee_certification == Player.RefereeCertification.NONE

    def test_parse_bool_variants(self):
        from hoops_planner.core.importers import _parse_bool

        assert _parse_bool("True") is True
        assert _parse_bool("true") is True
        assert _parse_bool("yes") is True
        assert _parse_bool("1") is True
        assert _parse_bool("on") is True
        assert _parse_bool("False") is False
        assert _parse_bool("no") is False
        assert _parse_bool("0") is False
        assert _parse_bool("") is False

    def test_import_without_upsert_creates_duplicates(self):
        """Without upsert, importing twice creates duplicate players."""
        import_members(MEMBERS_CSV, upsert=False)
        result = import_members(MEMBERS_CSV, upsert=False)
        assert result["players_created"] == 4
        assert Player.objects.count() == 8

    def test_import_without_upsert_creates_players(self):
        """Without upsert, players are created fresh."""
        result = import_members(MEMBERS_CSV, upsert=False)
        assert result["players_created"] == 4
        assert Player.objects.count() == 4
