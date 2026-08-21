"""Populate the database with demo data for local development / debugging.

Usage:
    uv run manage.py seed_demo             # wipe club data, then seed (default)
    uv run manage.py seed_demo --no-flush  # merge instead of wiping

By default the command wipes ALL games, tasks, assignments, players and teams
(and any non-demo seasons) before seeding, so you always get a clean, known
state. Pass ``--no-flush`` to keep existing data and only upsert the demo
users/teams/players plus rebuild the demo season.
"""

from typing import cast

from django.core.management.base import BaseCommand

from hoops_planner.core.demo_seed import DEMO_SEASONS, seed_demo_data
from hoops_planner.core.models import Game, Player, Season, Task, Team


class Command(BaseCommand):
    help = (
        "Seed the database with demo users, teams, players and schedules. "
        "Wipes existing club data first (use --no-flush to keep it)."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--no-flush",
            action="store_true",
            help=(
                "Keep existing data and only upsert demo users/teams/players "
                "plus rebuild the demo season, instead of wiping everything."
            ),
        )

    def handle(self, *args, **options) -> None:
        if not options["no_flush"]:
            self._flush()

        summary = seed_demo_data()

        self.stdout.write(self.style.SUCCESS("Seeded demo data:"))
        self.stdout.write(f"  users:       {summary['users']}")
        self.stdout.write(f"  teams:       {summary['teams']}")
        self.stdout.write(f"  players:     {summary['players']}")
        self.stdout.write(f"  seasons:     {summary['seasons']}")
        self.stdout.write(f"  games:       {summary['games']}")
        self.stdout.write(f"  assignments: {summary['assignments']}")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo seasons:"))
        for name in DEMO_SEASONS:
            self.stdout.write(f"  - {name}")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Log in with:"))
        credentials = cast(list[dict[str, str]], summary["credentials"])
        for cred in credentials:
            self.stdout.write(f"  {cred['username']:<10} / {cred['password']}")

    def _flush(self) -> None:
        """Remove club data so the seed starts from a clean slate."""
        Game.objects.all().delete()
        Task.objects.all().delete()
        Player.objects.all().delete()
        Team.objects.all().delete()
        # Keep user accounts; only drop non-demo seasons.
        Season.objects.exclude(name__in=DEMO_SEASONS).delete()
        self.stdout.write("Flushed existing club data.")
