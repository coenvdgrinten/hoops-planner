"""Core models for the Hoops Planner."""

from django.db import models


class Team(models.Model):
    """A basketball team within the club."""

    class AgeCategory(models.TextChoices):
        X10 = "X10", "X10"
        X12 = "X12", "X12"
        X14 = "X14", "X14"
        X16 = "X16", "X16"
        VSE = "VSE", "VSE"
        M16 = "M16", "M16"
        M18 = "M18", "M18"
        M22 = "M22", "M22"
        MSE = "MSE", "MSE"

    name = models.CharField(max_length=100, unique=True)  # e.g. "Vido X10-1"
    age_category = models.CharField(
        max_length=10,
        choices=AgeCategory.choices,
    )
    requires_24_second_operator = models.BooleanField(
        default=False,
        help_text="Whether this team requires a 24-second operator for their games.",
    )

    class Meta:
        ordering = ["age_category", "name"]

    def __str__(self) -> str:
        return self.name


class Player(models.Model):
    """A club member who can be assigned tasks."""

    class RefereeCertification(models.TextChoices):
        NONE = "NONE", "None"
        F = "F", "F-diploma"
        SENIOR = "SENIOR", "Senior"

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="players",
    )
    is_coach = models.BooleanField(default=False)
    referee_certification = models.CharField(
        max_length=10,
        choices=RefereeCertification.choices,
        default=RefereeCertification.NONE,
    )

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Season(models.Model):
    """A basketball season."""

    name = models.CharField(max_length=50, unique=True)  # e.g. "2025-2026"

    class Meta:
        ordering = ["-name"]

    def __str__(self) -> str:
        return self.name


class Game(models.Model):
    """A scheduled game."""

    class GameType(models.TextChoices):
        HOME = "HOME", "Home"
        AWAY = "AWAY", "Away"

    class Court(models.TextChoices):
        COURT_1 = "1", "Court 1"
        COURT_2 = "2", "Court 2"

    season = models.ForeignKey(
        Season,
        on_delete=models.CASCADE,
        related_name="games",
    )
    home_team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="home_games",
    )
    away_team = models.CharField(max_length=100)  # e.g. "Achilles '71"
    game_type = models.CharField(
        max_length=10,
        choices=GameType.choices,
        default=GameType.HOME,
    )
    date = models.DateField()
    time = models.TimeField()
    court = models.CharField(
        max_length=1,
        choices=Court.choices,
    )
    required_referees = models.PositiveIntegerField(
        default=2,
        help_text="Number of referees needed for this game's age category.",
    )

    class Meta:
        ordering = ["date", "time", "court"]
        # Prevent games on the same court at the same time within a season
        unique_together = ["season", "date", "time", "court"]

    def __str__(self) -> str:
        return f"{self.home_team} vs {self.away_team} ({self.date})"

    @property
    def time_slot_key(self) -> str:
        """Unique key for the time slot (date + time)."""
        return f"{self.date}T{self.time}"


class TaskType(models.TextChoices):
    REFEREE = "REFEREE", "Referee"
    SCORER = "SCORER", "Scorer"
    TIMER = "TIMER", "Timer"
    SECOND_24_OPERATOR = "24_SECOND_OPERATOR", "24 Second Operator"


class Task(models.Model):
    """A task slot that needs to be filled for a game."""

    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    task_type = models.CharField(
        max_length=20,
        choices=TaskType.choices,
    )
    slot_number = models.PositiveIntegerField(
        default=1,
        help_text=(
            "Slot number for tasks that need multiple people "
            "(e.g., Referee 1, Referee 2)."
        ),
    )

    class Meta:
        ordering = ["task_type", "slot_number", "game"]
        unique_together = ["game", "task_type", "slot_number"]

    def __str__(self) -> str:
        return f"{self.get_task_type_display()} {self.slot_number} - {self.game}"


class TaskAssignment(models.Model):
    """An assignment of a player to a task."""

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    player = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["task", "player"]

    def __str__(self) -> str:
        return f"{self.player} -> {self.task}"
