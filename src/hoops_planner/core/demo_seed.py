"""Idempotent demo-data seeder for local development and e2e debugging.

Populates the database with a small, realistic club so you can log in and
click around without importing CSVs by hand:

* a few users with known credentials (plus the ``admin`` account),
* 12 teams spread across mixed age categories,
* a roster of players (including coaches and certified referees),
* one season of scheduled games (built with the same ``import_schedule``
  logic the app uses, so task slots are created identically), and
* a handful of valid task assignments (chosen via the real eligibility rules).

Re-running is safe: users/teams/players are upserted, and the demo season is
rebuilt from scratch (its games, tasks and assignments are replaced). Any
other season you created is left alone.

Run it either way:

* management command:  ``uv run manage.py seed_demo``
* admin API (DEBUG):   ``POST /api/seed/``  (used by the Playwright fixture)
"""

from __future__ import annotations

import datetime as dt

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

from hoops_planner.core.eligibility import get_eligible_players
from hoops_planner.core.importers import import_schedule
from hoops_planner.core.models import (
    Game,
    Player,
    Season,
    TaskAssignment,
    Team,
)

# ---------------------------------------------------------------------------
# Fixed demo identifiers
# ---------------------------------------------------------------------------

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"

# Each demo account's password equals its username.
DEMO_USERS: list[dict[str, str]] = [
    {"username": "planner", "password": "planner", "email": "planner@bcvido.example"},
    {"username": "coach", "password": "coach", "email": "coach@bcvido.example"},
]

# The single season that gets (re)built on every run.
DEMO_SEASONS = ["2025-2026"]

# 12 teams across mixed age categories. Kids teams (X10/X12) use
# parent_responsible so parents fill scorer/timer roles.
TEAMS: list[dict[str, str | bool]] = [
    {"name": "Vido X10-1", "age_category": "X10", "parent_responsible": True},
    {"name": "Vido X10-2", "age_category": "X10", "parent_responsible": True},
    {"name": "Vido X12-1", "age_category": "X12", "parent_responsible": True},
    {"name": "Vido X14-1", "age_category": "X14"},
    {"name": "Vido X14-2", "age_category": "X14"},
    {"name": "Vido X16-1", "age_category": "X16"},
    {"name": "Vido M16-1", "age_category": "M16"},
    {"name": "Vido M18-1", "age_category": "M18"},
    {"name": "Vido M22-1", "age_category": "M22"},
    {"name": "Vido VSE1", "age_category": "VSE"},
    {"name": "Vido VSE2", "age_category": "VSE"},
    {"name": "Vido MSE1", "age_category": "MSE"},
]

# Per-team roster. Each entry: (first_name, last_name, is_coach, cert).
# Adult teams carry certified referees (F / SENIOR) so referee tasks have
# eligible candidates.
ROSTERS: dict[str, list[tuple[str, str, bool, str]]] = {
    "Vido X10-1": [
        ("Koen", "Peeters", True, "NONE"),
        ("Jan", "Janssens", False, "NONE"),
        ("Pieter", "Van Damme", False, "NONE"),
        ("Luc", "Delaere", False, "NONE"),
        ("Louis", "Wijnendaele", False, "NONE"),
    ],
    "Vido X10-2": [
        ("Mathis", "Demeyer", True, "NONE"),
        ("Elias", "Peeters", False, "NONE"),
        ("Noah", "Janssen", False, "NONE"),
        ("Sem", "Hendrickx", False, "NONE"),
        ("Liam", "Vermeulen", False, "NONE"),
    ],
    "Vido X12-1": [
        ("Finn", "De Smet", True, "NONE"),
        ("Thomas", "Baert", False, "NONE"),
        ("Julien", "Van Den Berg", False, "NONE"),
        ("Maxime", "Clercx", False, "NONE"),
        ("Daan", "Verstraete", False, "NONE"),
    ],
    "Vido X14-1": [
        ("Bart", "Huybrechts", True, "NONE"),
        ("Tim", "Van Den Berg", False, "NONE"),
        ("Sven", "De Smet", False, "T1"),
        ("Jelle", "Van Looy", False, "T1"),
        ("Ruben", "Peeters", False, "T3"),
    ],
    "Vido X14-2": [
        ("Wouter", "De Clercq", True, "NONE"),
        ("Dries", "Van Looy", False, "NONE"),
        ("Mathias", "Clercx", False, "NONE"),
        ("Stan", "Van Damme", False, "T1"),
        ("Lars", "De Boeck", False, "T4"),
    ],
    "Vido X16-1": [
        ("Anke", "Van Dun", True, "NONE"),
        ("Iris", "Van Driel", False, "NONE"),
        ("Farah", "Koeiman", False, "NONE"),
        ("Saskia", "Douben", False, "NONE"),
        ("Imke", "Steenbergen", False, "F"),
    ],
    "Vido M16-1": [
        ("Rik", "Van Dam", True, "NONE"),
        ("Michael", "Heertum", False, "NONE"),
        ("Coen", "Grinten", False, "NONE"),
        ("Dani", "Peeters", False, "NONE"),
        ("Jan", "Hulva", False, "F"),
    ],
    "Vido M18-1": [
        ("Raoul", "Overeem", True, "NONE"),
        ("Kylian", "Keller", False, "NONE"),
        ("Laurens", "Kolenbrander", False, "NONE"),
        ("Ian", "Mennings", False, "NONE"),
        ("Milan", "Dalen", False, "SENIOR"),
        ("Emre", "Yarlligan", False, "F"),
    ],
    "Vido M22-1": [
        ("Sami", "Said", True, "NONE"),
        ("Skip", "Van Laarhoven", False, "NONE"),
        ("Bram", "Van Der Lee", False, "NONE"),
        ("Guus", "Hamelink", False, "NONE"),
        ("Nemanja", "Jonanovic", False, "SENIOR"),
        ("Davis", "Sevo", False, "F"),
    ],
    "Vido VSE1": [
        ("Sonja", "Adamovica", True, "NONE"),
        ("Tharwa", "Albezreh", False, "NONE"),
        ("Hanneke", "Van Wierst", False, "F"),
        ("Saskia", "Thus", False, "F"),
        ("Iris", "Van Driel", False, "SENIOR"),
    ],
    "Vido VSE2": [
        ("Anke", "Van Dun", True, "NONE"),
        ("Farah", "Koeiman", False, "NONE"),
        ("Saskia", "Douben", False, "F"),
        ("Imke", "Steenbergen", False, "F"),
        ("Hanneke", "Van Wierst", False, "SENIOR"),
    ],
    "Vido MSE1": [
        ("Rik", "Van Dam", True, "NONE"),
        ("Michael", "Heertum", False, "NONE"),
        ("Coen", "Grinten", False, "SENIOR"),
        ("Dani", "Peeters", False, "F"),
        ("Thomas", "Van Dongen", False, "F"),
    ],
}

# Opponent clubs used to fill the schedules.
OPPONENTS = [
    "Achilles '71",
    "BC Roeselare",
    "Trajanum",
    "Almonte",
    "Attacus",
    "BC Knokke",
    "BC Ieper",
    "BC Tongeren",
    "Jumping Giants",
    "Tantalus",
    "BC Oostende",
    "Rush",
    "Belair",
]

# Match days for the demo season (ISO dates).
SEASON_DATES: dict[str, list[dt.date]] = {
    "2025-2026": [
        dt.date(2025, 10, 4),
        dt.date(2025, 10, 18),
        dt.date(2025, 11, 1),
        dt.date(2025, 11, 15),
    ],
}

_TIMES = ["13:00", "14:30", "16:00", "17:30"]
_COURTS = ["1", "2"]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def seed_demo_data() -> dict[str, object]:
    """Create/refresh all demo data. Returns a summary of object counts."""
    _ensure_admin()
    _ensure_users()
    _ensure_teams()
    _ensure_players()
    games_created = _ensure_schedules()
    assignments_created = _seed_assignments()
    return {
        "users": User.objects.count(),
        "teams": Team.objects.count(),
        "players": Player.objects.count(),
        "seasons": Season.objects.count(),
        "games": Game.objects.count(),
        "games_created_this_run": games_created,
        "assignments": TaskAssignment.objects.count(),
        "assignments_created_this_run": assignments_created,
        "demo_seasons": DEMO_SEASONS,
        "credentials": [
            {"username": u["username"], "password": u["password"]} for u in DEMO_USERS
        ]
        + [{"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}],
    }


# ---------------------------------------------------------------------------
# Internal steps
# ---------------------------------------------------------------------------


def _ensure_admin() -> None:
    admin, _ = User.objects.get_or_create(
        username=ADMIN_USERNAME,
        defaults={
            "email": "admin@example.com",
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        },
    )
    # Always reset the password so re-seeding keeps credentials predictable.
    admin.set_password(ADMIN_PASSWORD)
    admin.is_staff = True
    admin.is_superuser = True
    admin.is_active = True
    admin.save()
    Token.objects.get_or_create(user=admin)


def _ensure_users() -> None:
    for spec in DEMO_USERS:
        user, _ = User.objects.get_or_create(
            username=spec["username"],
            defaults={"email": spec["email"], "is_active": True},
        )
        # Always reset the password so re-seeding keeps credentials predictable.
        user.set_password(spec["password"])
        user.is_active = True
        user.save()
        Token.objects.get_or_create(user=user)


def _ensure_teams() -> None:
    for spec in TEAMS:
        team, _ = Team.objects.get_or_create(
            name=spec["name"],
            defaults={
                "age_category": spec["age_category"],
                "required_referees": 2,
                "optional_referees": 0,
                "require_scorer": True,
                "require_timer": True,
                "requires_24_second_operator": False,
                "parent_responsible": spec.get("parent_responsible", False),
            },
        )
        # Keep staffing settings stable across runs.
        updates = {
            "age_category": spec["age_category"],
            "required_referees": 2,
            "require_scorer": True,
            "require_timer": True,
            "parent_responsible": spec.get("parent_responsible", False),
        }
        changed = any(getattr(team, k) != v for k, v in updates.items())
        if changed:
            for k, v in updates.items():
                setattr(team, k, v)
            team.save(update_fields=list(updates))


def _ensure_players() -> None:
    for team_spec in TEAMS:
        team = Team.objects.get(name=team_spec["name"])
        for first, last, is_coach, cert in ROSTERS.get(team.name, []):
            Player.objects.update_or_create(
                first_name=first,
                last_name=last,
                team=team,
                defaults={"is_coach": is_coach, "referee_certification": cert},
            )


def _build_schedule_csv(season_name: str) -> str:
    """Build a schedule CSV for a season from its match days."""
    dates = SEASON_DATES[season_name]
    team_names = [t["name"] for t in TEAMS]
    lines = ["date,time,court,home_team,away_team,game_type,half"]
    idx = 0
    for day in dates:
        half = "1" if day.month in (9, 10, 11, 12) else "2"
        for time_slot in _TIMES:
            for court in _COURTS:
                own_team = team_names[idx % len(team_names)]
                opponent = OPPONENTS[idx % len(OPPONENTS)]
                # Sprinkle in some away games so the Availability view has data.
                game_type = "AWAY" if idx % 5 == 3 else "HOME"
                lines.append(
                    f"{day.isoformat()},{time_slot},{court},"
                    f"{own_team},{opponent},{game_type},{half}"
                )
                idx += 1
    return "\n".join(lines) + "\n"


def _ensure_schedules() -> int:
    """(Re)build the demo seasons. Returns number of games created."""
    total_created = 0
    for season_name in DEMO_SEASONS:
        csv_text = _build_schedule_csv(season_name)
        result = import_schedule(csv_text, season_name, replace=True)
        total_created += result["games_created"]
    return total_created


def _seed_assignments(max_games: int = 10) -> int:
    """Fill task slots for the first season's earliest games.

    Uses the real eligibility rules so every assignment is valid, and stops
    gracefully when no eligible player remains for a slot.
    """
    season = Season.objects.filter(name=DEMO_SEASONS[0]).first()
    if season is None:
        return 0

    count = 0
    games = list(season.games.order_by("date", "time", "court")[:max_games])
    for game in games:
        for task in game.tasks.all():
            eligible = get_eligible_players(task)
            if not eligible:
                continue
            TaskAssignment.objects.get_or_create(task=task, player=eligible[0])
            count += 1
    return count
