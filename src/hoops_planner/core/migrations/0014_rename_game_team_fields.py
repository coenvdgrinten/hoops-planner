"""Rename Game.home_team -> own_team and Game.away_team -> opponent.

Standardizes the away-game data convention: ``own_team`` is always the club
team the game is for (home or away), and ``opponent`` is the external team.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_player_is_exempt"),
    ]

    operations = [
        migrations.RenameField(
            model_name="game",
            old_name="home_team",
            new_name="own_team",
        ),
        migrations.RenameField(
            model_name="game",
            old_name="away_team",
            new_name="opponent",
        ),
    ]
