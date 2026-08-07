"""Add is_exempt field to Player model."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_game_location_alter_team_parent_responsible"),
    ]

    operations = [
        migrations.AddField(
            model_name="player",
            name="is_exempt",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Whether this player is exempt from task assignments "
                    "(e.g., board members)."
                ),
            ),
        ),
    ]
