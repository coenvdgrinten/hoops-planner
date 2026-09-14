"""Tests for schedule versions (issue #3).

Covers the payload builder, content hash, per-season numbering, latest-version
dedupe, and the ``save_version``/``note`` params on the PDF/CSV export
endpoints.
"""

import datetime as dt

import pytest

from hoops_planner.core.models import (
    Game,
    ScheduleVersion,
    Task,
    TaskAssignment,
    TaskType,
)
from hoops_planner.core.schedule_versions import (
    build_payload,
    content_hash,
    save_version,
)


def _make_game(season, team, **overrides):
    defaults = dict(
        season=season,
        own_team=team,
        opponent="Opponent",
        game_type=Game.GameType.HOME,
        date=dt.date(2025, 10, 1),
        time=dt.time(14, 0),
        court=Game.Court.COURT_1,
        half=Game.Half.FIRST,
    )
    defaults.update(overrides)
    return Game.objects.create(**defaults)


@pytest.mark.django_db
class TestBuildPayload:
    def test_shape_and_canonical_fields(self, season, team_x14, player):
        game = _make_game(season, team_x14)
        task = Task.objects.create(game=game, task_type=TaskType.REFEREE, slot_number=1)
        TaskAssignment.objects.create(task=task, player=player)

        payload = build_payload(season)

        assert payload["season"] == {"id": season.id, "name": season.name}
        assert len(payload["games"]) == 1
        g = payload["games"][0]
        assert g["id"] == game.id
        assert g["date"] == "2025-10-01"
        assert g["time"] == "14:00"
        assert g["court"] == "1"
        assert g["half"] == "1"
        assert g["game_type"] == "HOME"
        assert g["location"] == "Den Ekkerman"
        assert g["own_team"] == {"id": team_x14.id, "name": team_x14.name}
        assert g["opponent"] == "Opponent"
        assert len(g["tasks"]) == 1
        t = g["tasks"][0]
        assert t["id"] == task.id
        assert t["task_type"] == "REFEREE"
        assert t["slot_number"] == 1
        assert t["optional"] is False
        assert t["assignment"] == {
            "player_id": player.id,
            "player_name": player.full_name,
            "team_id": team_x14.id,
            "team_name": team_x14.name,
        }

    def test_unassigned_task_has_null_assignment(self, season, team_x14):
        game = _make_game(season, team_x14)
        Task.objects.create(game=game, task_type=TaskType.SCORER, slot_number=1)

        payload = build_payload(season)
        assert payload["games"][0]["tasks"][0]["assignment"] is None

    def test_whole_season_includes_all_halves(self, season, team_x14):
        _make_game(season, team_x14, half=Game.Half.FIRST)
        _make_game(
            season,
            team_x14,
            half=Game.Half.SECOND,
            date=dt.date(2026, 1, 10),
            court=Game.Court.COURT_2,
        )

        payload = build_payload(season)
        halves = {g["half"] for g in payload["games"]}
        assert halves == {"1", "2"}

    def test_games_ordered_by_date_time_court(self, season, team_x14, team_mse):
        _make_game(season, team_mse, date=dt.date(2025, 10, 8))
        _make_game(season, team_x14)
        _make_game(
            season,
            team_x14,
            court=Game.Court.COURT_2,
        )  # same date/time as first game, other court

        payload = build_payload(season)
        order = [(g["date"], g["time"], g["court"]) for g in payload["games"]]
        assert order == [
            ("2025-10-01", "14:00", "1"),
            ("2025-10-01", "14:00", "2"),
            ("2025-10-08", "14:00", "1"),
        ]

    def test_empty_season(self, season):
        assert build_payload(season) == {
            "season": {"id": season.id, "name": season.name},
            "games": [],
        }


@pytest.mark.django_db
class TestContentHash:
    def test_stable_across_builds(self, season, team_x14, player):
        game = _make_game(season, team_x14)
        task = Task.objects.create(game=game, task_type=TaskType.REFEREE, slot_number=1)
        TaskAssignment.objects.create(task=task, player=player)

        assert content_hash(build_payload(season)) == content_hash(
            build_payload(season)
        )

    def test_changes_when_schedule_changes(self, season, team_x14, player):
        game = _make_game(season, team_x14)
        task = Task.objects.create(game=game, task_type=TaskType.REFEREE, slot_number=1)
        before = content_hash(build_payload(season))
        TaskAssignment.objects.create(task=task, player=player)
        after = content_hash(build_payload(season))
        assert before != after


@pytest.mark.django_db
class TestSaveVersion:
    def test_first_save_is_v1(self, season):
        result = save_version(season, "first send")
        assert result.saved is True
        assert result.version_number == 1
        assert "v1" in result.message
        version = ScheduleVersion.objects.get(season=season)
        assert version.number == 1
        assert version.note == "first send"
        assert len(version.content_hash) == 64

    def test_identical_content_dedupes_against_latest(self, season):
        save_version(season)
        result = save_version(season)
        assert result.saved is False
        assert result.version_number == 1
        assert "No changes since v1" in result.message
        assert "—" not in result.message  # header-safe (ASCII only)
        assert ScheduleVersion.objects.filter(season=season).count() == 1

    def test_changed_content_creates_next_number(self, season, team_x14, player):
        save_version(season)
        game = _make_game(season, team_x14)
        task = Task.objects.create(game=game, task_type=TaskType.SCORER, slot_number=1)
        TaskAssignment.objects.create(task=task, player=player)

        result = save_version(season)
        assert result.saved is True
        assert result.version_number == 2
        numbers = list(
            ScheduleVersion.objects.filter(season=season).order_by("number").values_list(
                "number", flat=True
            )
        )
        assert numbers == [1, 2]

    def test_note_is_stripped(self, season):
        result = save_version(season, "  sent to teams  ")
        version = ScheduleVersion.objects.get(pk=result.version_number)
        assert version.note == "sent to teams"

    def test_versions_are_per_season(self, season, team_x14):
        from hoops_planner.core.models import Season

        other = Season.objects.create(name="2026-2027")
        r1 = save_version(season)
        r2 = save_version(other)
        assert r1.version_number == 1
        assert r2.version_number == 1
        assert ScheduleVersion.objects.count() == 2

    def test_payload_round_trips_through_json_field(self, season, team_x14, player):
        game = _make_game(season, team_x14)
        task = Task.objects.create(game=game, task_type=TaskType.REFEREE, slot_number=1)
        TaskAssignment.objects.create(task=task, player=player)
        result = save_version(season)

        stored = ScheduleVersion.objects.get(pk=result.version_number).payload
        assert stored == build_payload(season)


@pytest.mark.django_db
class TestExportEndpoints:
    """The save_version/note query params on export_pdf / export_csv."""

    def test_export_csv_without_param_saves_nothing(self, api_client, season):
        response = api_client.get(f"/api/seasons/{season.id}/export_csv/")
        assert response.status_code == 200
        assert ScheduleVersion.objects.count() == 0
        disposition = response["Content-Disposition"]
        assert "_v" not in disposition
        assert "X-Schedule-Version-Status" not in response

    def test_export_csv_with_save_version_stores_v1(self, api_client, season):
        response = api_client.get(
            f"/api/seasons/{season.id}/export_csv/?save_version=1&note=first+send"
        )
        assert response.status_code == 200
        version = ScheduleVersion.objects.get(season=season)
        assert version.number == 1
        assert version.note == "first send"
        # Filename carries the version suffix so download matches the snapshot.
        assert "_v1.csv" in response["Content-Disposition"]
        # The UI reads the outcome from these headers.
        assert response["X-Schedule-Version"] == "v1"
        assert response["X-Schedule-Version-Status"] == "saved"
        assert "v1" in response["X-Schedule-Version-Message"]

    def test_export_pdf_with_save_version_stores_v1(self, api_client, season):
        response = api_client.get(
            f"/api/seasons/{season.id}/export_pdf/?save_version=1"
        )
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert ScheduleVersion.objects.filter(season=season).count() == 1
        assert "_v1.pdf" in response["Content-Disposition"]
        assert response["X-Schedule-Version"] == "v1"

    def test_second_identical_export_does_not_create_new_version(
        self, api_client, season
    ):
        api_client.get(f"/api/seasons/{season.id}/export_csv/?save_version=1")
        response = api_client.get(
            f"/api/seasons/{season.id}/export_csv/?save_version=1"
        )
        assert response.status_code == 200
        assert ScheduleVersion.objects.filter(season=season).count() == 1
        # No new version → no suffix on the second download…
        assert "_v" not in response["Content-Disposition"]
        # …and the dedupe is reported, not silent.
        assert response["X-Schedule-Version-Status"] == "skipped"
        assert "No changes since v1" in response["X-Schedule-Version-Message"]
        assert "X-Schedule-Version" not in response

    def test_changed_schedule_creates_v2_on_next_export(
        self, api_client, season, team_x14, player
    ):
        api_client.get(f"/api/seasons/{season.id}/export_csv/?save_version=1")
        game = _make_game(season, team_x14)
        task = Task.objects.create(game=game, task_type=TaskType.SCORER, slot_number=1)
        TaskAssignment.objects.create(task=task, player=player)

        response = api_client.get(
            f"/api/seasons/{season.id}/export_csv/?save_version=1"
        )
        assert response.status_code == 200
        assert ScheduleVersion.objects.filter(season=season).count() == 2
        assert "_v2.csv" in response["Content-Disposition"]
