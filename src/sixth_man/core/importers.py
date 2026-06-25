"""CSV import logic for schedules and members."""

import csv
import io
import re

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
) -> dict[str, int]:
    """Import a schedule CSV and create games + task slots.

    Expected CSV columns:
    date, time, court, home_team, away_team

    Returns a summary dict with counts of created objects.
    """
    season, _ = Season.objects.get_or_create(name=season_name)
    
    # Delete existing games for this season to allow re-importing.
    # Tasks and assignments are CASCADE-deleted through foreign keys.
    Game.objects.filter(season=season).delete()
    
    created = {"games": 0, "tasks": 0}

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

        game, is_new = Game.objects.get_or_create(
            season=season,
            home_team=home_team,
            away_team=row["away_team"].strip(),
            date=row["date"].strip(),
            time=row["time"].strip(),
            court=row["court"].strip(),
            defaults={"game_type": Game.GameType.HOME},
        )
        if is_new:
            created["games"] += 1
            created["tasks"] += _ensure_task_slots(game)

    return created


def _ensure_task_slots(game: Game) -> int:
    """Create task slots for a game if they don't already exist.

    Returns the number of task slots created.
    """
    tasks_to_create: list[Task] = []

    # Scorer — always needed
    tasks_to_create.append(Task(game=game, task_type=TaskType.SCORER, slot_number=1))

    # Timer — always needed
    tasks_to_create.append(Task(game=game, task_type=TaskType.TIMER, slot_number=1))

    # 24 Second Operator — depends on team setting
    if game.home_team.requires_24_second_operator:
        tasks_to_create.append(
            Task(game=game, task_type=TaskType.SECOND_24_OPERATOR, slot_number=1)
        )

    # Referees — configurable per game
    num_referees = int(game.required_referees)
    for slot in range(1, num_referees + 1):
        tasks_to_create.append(
            Task(game=game, task_type=TaskType.REFEREE, slot_number=slot)
        )

    count = 0
    for task in tasks_to_create:
        _, was_created = Task.objects.get_or_create(
            game=game,
            task_type=task.task_type,
            slot_number=task.slot_number,
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
            if re.search(rf"\b{re.escape(category)}\d*(?![a-zA-Z])", team_name, re.IGNORECASE):
                return category
    return Team.AgeCategory.X14  # sensible default


def import_members(
    csv_text: str,
    upsert: bool = True,
) -> dict[str, int]:
    """Import a members CSV and create or update players and teams.

    Expected CSV columns:
    first_name, last_name, team, is_coach, referee_certification

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
            if not is_new:
                player.team = team
                player.is_coach = is_coach
                player.referee_certification = cert
                player.save()
                created["players_updated"] += 1
            else:
                created["players_created"] += 1
        else:
            Player.objects.create(
                first_name=first_name,
                last_name=last_name,
                team=team,
                is_coach=is_coach,
                referee_certification=cert,
            )
            created["players_created"] += 1

    return created


def _parse_bool(value: str) -> bool:
    """Parse a boolean from common string representations."""
    return value.strip().lower() in ("true", "yes", "1", "on")
