"""CSV import logic for schedules and members."""

import csv
import io
import re
from datetime import datetime
from typing import Any

from sixth_man.core.models import (
    Game,
    Player,
    Season,
    Task,
    TaskType,
    Team,
)


def import_schedule(
    csv_text: str,
    season_name: str,
    replace: bool = False,
) -> dict[str, int]:
    """Import a schedule CSV and create or update games + task slots.

    Expected CSV columns:
    date, time, court, home_team, away_team

    Optional CSV columns:
    half — 1 or 2 (defaults to 1)
    game_type — "HOME" or "AWAY" (defaults to "HOME"). For away games the
        home_team column still names the team that plays at home (the club's
        opponent), while away_team names the club's travelling team.

    Parameters
    ----------
    csv_text : str
        The CSV content.
    season_name : str
        Name of the season (e.g. "2025-2026").
    replace : bool
        If True, delete all existing games for this season before importing.
        If False, match existing games by (date, time, court, home_team, away_team)
        and update changed fields; create new games for rows without a match.

    Returns a summary dict with counts of created/updated objects.
    """
    season, _ = Season.objects.get_or_create(name=season_name)

    if replace:
        # Destructive import: delete everything and start fresh.
        Game.objects.filter(season=season).delete()

    created = {"games_created": 0, "games_updated": 0, "tasks": 0}

    reader = csv.DictReader(io.StringIO(csv_text))
    rows = list(reader)

    for row in rows:
        home_team, _ = Team.objects.get_or_create(
            name=row["home_team"].strip(),
            defaults={
                "age_category": _infer_age_category(row["home_team"].strip()),
            },
        )
        # Fix age_category if it was wrong on first import
        expected_category = _infer_age_category(row["home_team"].strip())
        if home_team.age_category != expected_category:
            home_team.age_category = expected_category
            home_team.save(update_fields=["age_category"])

        # Parse optional half column
        half_raw = row.get("half", "").strip()
        half_value = half_raw if half_raw in ("1", "2") else Game.Half.FIRST

        # Parse optional game_type column (HOME or AWAY)
        game_type_raw = row.get("game_type", "").strip().upper()
        game_type_value = (
            game_type_raw
            if game_type_raw in Game.GameType.values
            else Game.GameType.HOME
        )

        # Build game data from CSV
        game_data = {
            "season": season,
            "home_team": home_team,
            "away_team": row["away_team"].strip(),
            "date": row["date"].strip(),
            "time": row["time"].strip(),
            "court": row["court"].strip(),
            "half": half_value,
            "game_type": game_type_value,
        }

        if replace:
            # In replace mode, just create everything fresh.
            game, is_new = Game.objects.get_or_create(
                season=season,
                date=game_data["date"],
                time=game_data["time"],
                court=game_data["court"],
                defaults=game_data,
            )
            if is_new:
                created["games_created"] += 1
                created["tasks"] += _ensure_task_slots(game)
        else:
            # Smart mode: try to match an existing game.
            game, is_new = _match_or_create_game(game_data)
            if is_new:
                created["games_created"] += 1
                created["tasks"] += _ensure_task_slots(game)
            else:
                # Update changed fields. Only check string/int fields to avoid
                # type mismatches (TimeField stores datetime.time, not str).
                # Skip fields used for matching (season, date, home_team).
                changed = False
                updatable = ("court", "half", "away_team", "game_type")
                for key in updatable:
                    value = game_data[key]
                    if getattr(game, key) != value:
                        setattr(game, key, value)
                        changed = True
                # For time, compare string representations
                csv_time = game_data["time"]
                db_time = game.time.strftime("%H:%M")
                if db_time != csv_time:
                    game.time = datetime.datetime.strptime(csv_time, "%H:%M").time()  # type: ignore[assignment]
                    changed = True
                if changed:
                    game.save(update_fields=list(updatable) + ["time"])
                    created["games_updated"] += 1

    return created


def _match_or_create_game(game_data: dict[str, Any]) -> tuple[Game, bool]:
    """Try to find an existing game matching the CSV row, or create one.

    Matching is done on (season, date, home_team, away_team) to handle
    cases where court or time changed but it's the same fixture.
    Falls back to (season, date, time, court) if no match on teams.
    """
    # Primary match: same date + same teams + same type (handles court/time changes)
    game = Game.objects.filter(
        season=game_data["season"],
        date=game_data["date"],
        home_team=game_data["home_team"],
        away_team=game_data["away_team"],
        game_type=game_data["game_type"],
    ).first()
    if game:
        return game, False

    # Secondary match: same date + time + court (handles opponent name changes)
    game = Game.objects.filter(
        season=game_data["season"],
        date=game_data["date"],
        time=game_data["time"],
        court=game_data["court"],
    ).first()
    if game:
        return game, False

    # No match — create new
    return Game.objects.create(**game_data), True


def _ensure_task_slots(game: Game) -> int:
    """Create task slots for a game if they don't already exist.

    Staffing (referees, scorer, timer, 24-second operator) is driven by the
    per-team settings on the game's home team.

    Returns the number of task slots created.
    """
    team = game.home_team
    tasks_to_create: list[Task] = []

    # Scorer — per-team setting
    if team.require_scorer:
        tasks_to_create.append(
            Task(game=game, task_type=TaskType.SCORER, slot_number=1)
        )

    # Timer — per-team setting
    if team.require_timer:
        tasks_to_create.append(Task(game=game, task_type=TaskType.TIMER, slot_number=1))

    # 24 Second Operator — per-team setting
    if team.requires_24_second_operator:
        tasks_to_create.append(
            Task(game=game, task_type=TaskType.SECOND_24_OPERATOR, slot_number=1)
        )

    # Referees — required slots first, then optional slots
    required = int(team.required_referees)
    optional = int(team.optional_referees)
    for slot in range(1, required + optional + 1):
        is_optional = slot > required
        tasks_to_create.append(
            Task(
                game=game,
                task_type=TaskType.REFEREE,
                slot_number=slot,
                optional=is_optional,
            )
        )

    count = 0
    for task in tasks_to_create:
        _, was_created = Task.objects.get_or_create(
            game=game,
            task_type=task.task_type,
            slot_number=task.slot_number,
            defaults={"optional": task.optional},
        )
        if was_created:
            count += 1
    return count


def _infer_age_category(team_name: str) -> str:
    """Infer the age category from a team name like 'Vido X14-1'.

    Handles team names with trailing digits (e.g., 'VSE1', 'MSE1') by allowing
    optional digits after non-numeric category codes.
    """
    for category in Team.AgeCategory.values:
        if category[-1].isdigit():
            # Numeric categories (X10, X14, M16, etc.): use word boundary
            # to prevent X10 from matching X100.
            if re.search(rf"\b{re.escape(category)}\b", team_name, re.IGNORECASE):
                return category
        else:
            # Non-numeric categories (VSE, MSE): allow optional trailing digits
            # (e.g., 'VSE1'), but not letters.
            if re.search(
                rf"\b{re.escape(category)}\d*(?![a-zA-Z])",
                team_name,
                re.IGNORECASE,
            ):
                return category
    return Team.AgeCategory.X14  # sensible default


def import_members(
    csv_text: str,
    upsert: bool = True,
) -> dict[str, int]:
    """Import a members CSV and create or update players and teams.

    Expected CSV columns:
    first_name, last_name, team, is_coach, referee_certification

    Optional CSV columns:
    coached_teams — comma-separated list of team names this player coaches

    referee_certification can be: NONE, T1, T2, T3, T4, T5, T6
    is_coach can be: True/False, yes/no, 1/0

    Returns a summary dict with counts of created/updated objects.
    """
    created = {"teams": 0, "players_created": 0, "players_updated": 0}

    reader = csv.DictReader(io.StringIO(csv_text))

    for row in reader:
        team_name = row["team"].strip()
        team, team_is_new = Team.objects.get_or_create(
            name=team_name,
            defaults={
                "age_category": _infer_age_category(team_name),
            },
        )
        if team_is_new:
            created["teams"] += 1

        first_name = row["first_name"].strip()
        last_name = row["last_name"].strip()
        is_coach = _parse_bool(row.get("is_coach", "False"))
        cert = row.get("referee_certification", "NONE").strip().upper()

        # Validate certification value
        if cert not in Player.RefereeCertification.values:
            cert = Player.RefereeCertification.NONE

        # Parse coached_teams if provided
        coached_teams_raw = row.get("coached_teams", "").strip()
        coached_team_names = [
            t.strip() for t in coached_teams_raw.split(",") if t.strip()
        ]
        coached_teams = []
        for ct_name in coached_team_names:
            ct, ct_is_new = Team.objects.get_or_create(
                name=ct_name,
                defaults={
                    "age_category": _infer_age_category(ct_name),
                },
            )
            coached_teams.append(ct)
            if ct_is_new:
                created["teams"] += 1

        if upsert:
            player, is_new = Player.objects.get_or_create(
                first_name=first_name,
                last_name=last_name,
                defaults={
                    "team": team,
                    "is_coach": is_coach,
                    "referee_certification": cert,
                },
            )
            if coached_teams:
                player.coached_teams.set(coached_teams)
            if not is_new:
                player.team = team
                player.is_coach = is_coach
                player.referee_certification = cert
                player.save()
                created["players_updated"] += 1
            else:
                created["players_created"] += 1
        else:
            player = Player.objects.create(
                first_name=first_name,
                last_name=last_name,
                team=team,
                is_coach=is_coach,
                referee_certification=cert,
            )
            if coached_teams:
                player.coached_teams.set(coached_teams)
            created["players_created"] += 1

    return created


def _parse_bool(value: str) -> bool:
    """Parse a boolean from common string representations."""
    return value.strip().lower() in ("true", "yes", "1", "on")
