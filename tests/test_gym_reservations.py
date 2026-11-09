"""Tests for the GymReservation model and SiteConfig gym settings."""

import datetime as dt

import pytest
from django.core.exceptions import ValidationError

from hoops_planner.core.models import GymReservation, Season, SiteConfig


@pytest.fixture
def reservation(season):
    return GymReservation.objects.create(
        season=season,
        date=dt.date(2025, 10, 1),
        start_time=dt.time(9, 0),
        end_time=dt.time(17, 0),
    )


@pytest.mark.django_db
class TestGymReservationModel:
    def test_str(self, reservation):
        assert str(reservation) == "2025-10-01 09:00\u201317:00"

    def test_str_zero_padded_times(self, season):
        r = GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(0, 5),
            end_time=dt.time(1, 0),
        )
        assert str(r) == "2025-10-01 00:05\u201301:00"

    def test_duration_minutes(self, reservation):
        assert reservation.duration_minutes == 480

    def test_duration_minutes_partial_hour(self, season):
        r = GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 2),
            start_time=dt.time(10, 15),
            end_time=dt.time(12, 45),
        )
        assert r.duration_minutes == 150

    def test_duration_one_minute(self, season):
        r = GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 2),
            start_time=dt.time(9, 0),
            end_time=dt.time(9, 1),
        )
        assert r.duration_minutes == 1

    def test_duration_full_day_boundary(self, season):
        r = GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 2),
            start_time=dt.time(0, 0),
            end_time=dt.time(23, 59),
        )
        assert r.duration_minutes == 1439

    def test_duration_discards_seconds(self, season):
        r = GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 2),
            start_time=dt.time(9, 0, 45),
            end_time=dt.time(10, 0, 30),
        )
        assert r.duration_minutes == 60

    def test_duration_zero_when_times_equal_bypasses_clean(self, season):
        r = GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 2),
            start_time=dt.time(12, 0),
            end_time=dt.time(12, 0),
        )
        assert r.duration_minutes == 0

    def test_duration_negative_when_end_before_start_bypasses_clean(self, season):
        r = GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 2),
            start_time=dt.time(17, 0),
            end_time=dt.time(9, 0),
        )
        assert r.duration_minutes < 0

    def test_note_default_empty(self, reservation):
        assert reservation.note == ""


@pytest.mark.django_db
class TestGymReservationOrdering:
    def test_composite_ordering(self, season):
        r1 = GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 5),
            start_time=dt.time(14, 0),
            end_time=dt.time(18, 0),
        )
        r2 = GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(13, 0),
        )
        r3 = GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(14, 0),
            end_time=dt.time(18, 0),
        )
        qs = list(GymReservation.objects.filter(season=season))
        assert qs == [r2, r3, r1]

    def test_ordering_by_date_key_alone(self, season):
        r1 = GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 5),
            start_time=dt.time(9, 0),
            end_time=dt.time(13, 0),
        )
        r2 = GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(13, 0),
        )
        qs = list(GymReservation.objects.filter(season=season))
        assert qs == [r2, r1]

    def test_ordering_by_start_time_key_alone(self, season):
        r1 = GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(14, 0),
            end_time=dt.time(18, 0),
        )
        r2 = GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(13, 0),
        )
        qs = list(GymReservation.objects.filter(season=season))
        assert qs == [r2, r1]

    def test_ordering_scopes_across_seasons(self, season):
        other = Season.objects.create(name="2024-2025")
        r_this = GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(13, 0),
        )
        r_other = GymReservation.objects.create(
            season=other,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(13, 0),
        )
        assert list(season.gym_reservations.all()) == [r_this]
        assert list(other.gym_reservations.all()) == [r_other]


@pytest.mark.django_db
class TestGymReservationFkBehavior:
    def test_cascade_delete_with_season(self, reservation, season):
        season.delete()
        assert not GymReservation.objects.exists()

    def test_related_name(self, season, reservation):
        assert reservation in season.gym_reservations.all()

    def test_reverse_manager_empty_for_new_season(self, season):
        assert season.gym_reservations.count() == 0

    def test_forward_fk_back_reference(self, reservation, season):
        assert reservation.season == season
        assert reservation.season_id == season.pk

    def test_deleting_one_reservation_keeps_others(self, season, reservation):
        other = GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 2),
            start_time=dt.time(9, 0),
            end_time=dt.time(13, 0),
        )
        reservation.delete()
        assert GymReservation.objects.count() == 1
        assert season.gym_reservations.count() == 1
        assert other in season.gym_reservations.all()


@pytest.mark.django_db
class TestImplicitBehaviors:
    def test_overlapping_reservations_allowed(self, season):
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(12, 0),
        )
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(11, 0),
            end_time=dt.time(14, 0),
        )
        assert GymReservation.objects.filter(season=season).count() == 2

    def test_identical_duplicate_reservations_allowed(self, season):
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(17, 0),
        )
        GymReservation.objects.create(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(17, 0),
        )
        assert GymReservation.objects.filter(season=season).count() == 2


@pytest.mark.django_db
class TestGymReservationValidation:
    def test_end_after_start_ok(self, season):
        r = GymReservation(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(17, 0),
        )
        r.full_clean()

    def test_end_before_start_fails(self, season):
        r = GymReservation(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(17, 0),
            end_time=dt.time(9, 0),
        )
        with pytest.raises(ValidationError) as exc_info:
            r.full_clean()
        assert "end_time" in exc_info.value.message_dict

    def test_end_equal_start_fails(self, season):
        r = GymReservation(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(12, 0),
            end_time=dt.time(12, 0),
        )
        with pytest.raises(ValidationError) as exc_info:
            r.full_clean()
        assert "end_time" in exc_info.value.message_dict

    def test_clean_error_message_text(self, season):
        r = GymReservation(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(17, 0),
            end_time=dt.time(9, 0),
        )
        with pytest.raises(ValidationError) as exc_info:
            r.clean()
        messages = exc_info.value.message_dict["end_time"]
        assert "End time must be after start time." in messages

    def test_clean_raises_on_direct_call(self, season):
        r = GymReservation(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(17, 0),
            end_time=dt.time(9, 0),
        )
        with pytest.raises(ValidationError):
            r.clean()

    def test_full_clean_rejects_note_over_200_chars(self, season):
        r = GymReservation(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(17, 0),
            note="x" * 201,
        )
        with pytest.raises(ValidationError) as exc_info:
            r.full_clean()
        assert "note" in exc_info.value.message_dict

    def test_full_clean_accepts_note_exactly_200_chars(self, season):
        r = GymReservation(
            season=season,
            date=dt.date(2025, 10, 1),
            start_time=dt.time(9, 0),
            end_time=dt.time(17, 0),
            note="x" * 200,
        )
        r.full_clean()


@pytest.mark.django_db
class TestSiteConfigGymSettings:
    def test_defaults(self):
        config = SiteConfig.load()
        assert config.gym_game_duration_minutes == 90
        assert config.gym_margin_before_minutes == 30
        assert config.gym_margin_after_minutes == 15

    def test_update_settings(self):
        config = SiteConfig.load()
        config.gym_game_duration_minutes = 60  # ty: ignore[invalid-assignment]
        config.gym_margin_before_minutes = 20  # ty: ignore[invalid-assignment]
        config.gym_margin_after_minutes = 10  # ty: ignore[invalid-assignment]
        config.save()

        fresh = SiteConfig.load()
        assert fresh.gym_game_duration_minutes == 60
        assert fresh.gym_margin_before_minutes == 20
        assert fresh.gym_margin_after_minutes == 10

    def test_gym_settings_zero_boundary(self):
        config = SiteConfig.load()
        config.gym_game_duration_minutes = 0  # ty: ignore[invalid-assignment]
        config.gym_margin_before_minutes = 0  # ty: ignore[invalid-assignment]
        config.gym_margin_after_minutes = 0  # ty: ignore[invalid-assignment]
        config.save()

        fresh = SiteConfig.load()
        assert fresh.gym_game_duration_minutes == 0
        assert fresh.gym_margin_before_minutes == 0
        assert fresh.gym_margin_after_minutes == 0

    def test_gym_settings_large_values(self):
        config = SiteConfig.load()
        config.gym_game_duration_minutes = 600  # ty: ignore[invalid-assignment]
        config.gym_margin_before_minutes = 120  # ty: ignore[invalid-assignment]
        config.gym_margin_after_minutes = 60  # ty: ignore[invalid-assignment]
        config.save()

        fresh = SiteConfig.load()
        assert fresh.gym_game_duration_minutes == 600
        assert fresh.gym_margin_before_minutes == 120
        assert fresh.gym_margin_after_minutes == 60

    def test_gym_settings_reject_negative_via_full_clean(self):
        config = SiteConfig.load()
        config.gym_game_duration_minutes = -1  # ty: ignore[invalid-assignment]
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert "gym_game_duration_minutes" in exc_info.value.message_dict

    def test_no_constraint_when_margin_exceeds_game_duration(self):
        config = SiteConfig.load()
        config.gym_game_duration_minutes = 60  # ty: ignore[invalid-assignment]
        config.gym_margin_before_minutes = 120  # ty: ignore[invalid-assignment]
        config.save()

        fresh = SiteConfig.load()
        assert fresh.gym_margin_before_minutes == 120
        assert fresh.gym_game_duration_minutes == 60

    def test_load_is_idempotent_singleton(self):
        c1 = SiteConfig.load()
        c2 = SiteConfig.load()
        c3 = SiteConfig.load()
        assert c1.pk == c2.pk == c3.pk == 1
        assert SiteConfig.objects.count() == 1

    def test_gym_update_preserves_other_fields(self):
        config = SiteConfig.load()
        config.club_name = "BC Vido"  # ty: ignore[invalid-assignment]
        config.save()

        config.gym_game_duration_minutes = 45  # ty: ignore[invalid-assignment]
        config.save(update_fields=["gym_game_duration_minutes"])

        fresh = SiteConfig.load()
        assert fresh.club_name == "BC Vido"
        assert fresh.gym_game_duration_minutes == 45
