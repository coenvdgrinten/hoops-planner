"""Factory helpers for tests — auto-loaded by pytest."""

import datetime as dt

import pytest
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient  # noqa: F401

from hoops_planner.core.models import (
    Game,
    Player,
    Season,
    Task,
    Team,
)


@pytest.fixture
def season():
    return Season.objects.create(name="2025-2026")


@pytest.fixture
def team_x10():
    return Team.objects.create(
        name="Vido X10-1",
        age_category=Team.AgeCategory.X10,
    )


@pytest.fixture
def team_x14():
    return Team.objects.create(
        name="Vido X14-1",
        age_category=Team.AgeCategory.X14,
    )


@pytest.fixture
def team_x16():
    return Team.objects.create(
        name="Vido X16-1",
        age_category=Team.AgeCategory.X16,
    )


@pytest.fixture
def team_mse():
    return Team.objects.create(
        name="Vido MSE1",
        age_category=Team.AgeCategory.MSE,
    )


@pytest.fixture
def player(team_x14):
    return Player.objects.create(
        first_name="John",
        last_name="Doe",
        team=team_x14,
    )


@pytest.fixture
def referee(team_x14):
    return Player.objects.create(
        first_name="Jane",
        last_name="Smith",
        team=team_x14,
        referee_certification=Player.RefereeCertification.F,
    )


@pytest.fixture
def coach(team_x14):
    return Player.objects.create(
        first_name="Coach",
        last_name="Karlos",
        team=team_x14,
        is_coach=True,
    )


@pytest.fixture
def game(season, team_x14):
    """Create a game where the player's team is NOT involved.

    This ensures the base fixture doesn't trigger the
    `_player_team_involved_in_game` disqualification.
    """
    own_team = Team.objects.create(
        name="Vido X10-1",
        age_category=Team.AgeCategory.X10,
    )
    return Game.objects.create(
        season=season,
        own_team=own_team,
        opponent="Achilles '71",
        game_type=Game.GameType.HOME,
        date=dt.date(2025, 10, 1),
        time=dt.time(14, 0),
        court=Game.Court.COURT_1,
    )


@pytest.fixture
def task(game):
    return Task.objects.create(
        game=game,
        task_type="SCORER",
        slot_number=1,
    )


@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        username="testuser",
        password="testpass123",
        email="test@example.com",
    )


@pytest.fixture
def api_client(test_user):
    """Authenticated API client for tests."""
    client = APIClient()
    token = Token.objects.create(user=test_user)
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client
