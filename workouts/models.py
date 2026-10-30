from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import Equipment, ExperienceLevel, PrimaryGoal


class MovementCategory(models.TextChoices):
    PUSH = "push", "Push"
    PULL = "pull", "Pull"
    LEGS = "legs", "Legs"
    CORE = "core", "Core"
    SKILL = "skill", "Skill"
    FULL_BODY = "full_body", "Full body"
    WARMUP = "warmup", "Warm-up"
    COOLDOWN = "cooldown", "Cool-down"


class MovementType(models.TextChoices):
    REPS = "reps", "Repetitions"
    HOLD = "hold", "Timed hold"


class Exercise(models.Model):
    """A single exercise: technique, guidance, and progression metadata.

    `difficulty_level` and `primary_goal_tags` drive plan generation;
    `easier_variation`/`harder_variation` let the guided session offer
    regressions or progressions appropriate to the user's level.
    """

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    category = models.CharField(max_length=12, choices=MovementCategory.choices)
    movement_type = models.CharField(max_length=10, choices=MovementType.choices, default=MovementType.REPS)
    difficulty_level = models.CharField(max_length=20, choices=ExperienceLevel.choices)

    target_muscles = models.CharField(max_length=200, blank=True)
    equipment_required = models.JSONField(default=list, blank=True, help_text="Equipment values; empty/['none'] means bodyweight only.")
    primary_goal_tags = models.JSONField(default=list, blank=True, help_text="PrimaryGoal values this exercise especially suits; empty suits all goals.")

    instructions = models.TextField(help_text="Step-by-step technique instructions.")
    breathing_guidance = models.TextField(blank=True)
    common_mistakes = models.TextField(blank=True)
    video_url = models.URLField(blank=True)

    default_rest_seconds = models.PositiveSmallIntegerField(default=60)
    default_sets = models.PositiveSmallIntegerField(default=3)
    default_reps = models.PositiveSmallIntegerField(null=True, blank=True)
    default_hold_seconds = models.PositiveSmallIntegerField(null=True, blank=True)

    easier_variation = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="harder_variations_of"
    )
    harder_variation = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="easier_variations_of"
    )

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def suits_equipment(self, available_equipment):
        required = set(self.equipment_required) - {Equipment.NONE}
        if not required:
            return True
        return required.issubset(set(available_equipment) | {Equipment.FULL_GYM})

    def suits_experience(self, experience_level):
        order = [ExperienceLevel.BEGINNER, ExperienceLevel.INTERMEDIATE, ExperienceLevel.ADVANCED]
        return order.index(self.difficulty_level) <= order.index(experience_level)


class WorkoutPlan(models.Model):
    """A generated training plan, snapshotting the inputs used to build it.

    Snapshotting goal/experience/equipment at generation time means a plan
    stays internally consistent even if the user's profile changes later;
    they can regenerate a new plan to pick up profile changes.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workout_plans")
    goal = models.CharField(max_length=20, choices=PrimaryGoal.choices)
    experience_level = models.CharField(max_length=20, choices=ExperienceLevel.choices)
    training_days_per_week = models.PositiveSmallIntegerField()
    session_duration_minutes = models.PositiveSmallIntegerField()
    equipment = models.JSONField(default=list, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user}'s plan ({self.get_goal_display()})"


class WorkoutPlanDay(models.Model):
    """One slot in a plan's repeating 7-day cycle (training day or rest)."""

    plan = models.ForeignKey(WorkoutPlan, on_delete=models.CASCADE, related_name="days")
    day_index = models.PositiveSmallIntegerField(help_text="0-6, position in the repeating weekly cycle.")
    label = models.CharField(max_length=50)
    is_rest_day = models.BooleanField(default=False)

    class Meta:
        ordering = ["day_index"]
        unique_together = ("plan", "day_index")

    def __str__(self):
        return f"{self.plan} - Day {self.day_index + 1}: {self.label}"

    @property
    def estimated_minutes(self):
        return sum(pe.estimated_minutes for pe in self.exercises.all())


class WorkoutPlanExercise(models.Model):
    plan_day = models.ForeignKey(WorkoutPlanDay, on_delete=models.CASCADE, related_name="exercises")
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT)
    order = models.PositiveSmallIntegerField(default=0)

    target_sets = models.PositiveSmallIntegerField(default=3)
    target_reps = models.PositiveSmallIntegerField(null=True, blank=True)
    target_hold_seconds = models.PositiveSmallIntegerField(null=True, blank=True)
    rest_seconds = models.PositiveSmallIntegerField(default=60)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.exercise.name} ({self.target_sets} sets)"

    @property
    def estimated_minutes(self):
        per_set_seconds = (self.target_hold_seconds or 30 if self.exercise.movement_type == MovementType.HOLD else 30)
        total_seconds = self.target_sets * (per_set_seconds + self.rest_seconds)
        return round(total_seconds / 60, 1)

    @property
    def target_display(self):
        if self.exercise.movement_type == MovementType.HOLD:
            return f"{self.target_sets} x {self.target_hold_seconds}s hold"
        return f"{self.target_sets} x {self.target_reps} reps"


class SessionStatus(models.TextChoices):
    IN_PROGRESS = "in_progress", "In progress"
    COMPLETED = "completed", "Completed"


class WorkoutSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workout_sessions")
    plan_day = models.ForeignKey(WorkoutPlanDay, on_delete=models.SET_NULL, null=True, blank=True, related_name="sessions")
    date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=15, choices=SessionStatus.choices, default=SessionStatus.IN_PROGRESS)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "-started_at"]

    def __str__(self):
        return f"{self.user}: {self.date} ({self.status})"


class ExerciseLog(models.Model):
    session = models.ForeignKey(WorkoutSession, on_delete=models.CASCADE, related_name="logs")
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT)
    set_number = models.PositiveSmallIntegerField()

    reps = models.PositiveSmallIntegerField(null=True, blank=True)
    hold_seconds = models.PositiveSmallIntegerField(null=True, blank=True)
    rest_taken_seconds = models.PositiveSmallIntegerField(null=True, blank=True)
    effort_rpe = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )

    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["exercise_id", "set_number"]

    def __str__(self):
        return f"{self.exercise.name} set {self.set_number}"


class RecoveryNote(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recovery_notes")
    date = models.DateField(default=timezone.localdate)
    sleep_quality = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    soreness = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    fatigue = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]
        unique_together = ("user", "date")

    def __str__(self):
        return f"{self.user}: recovery on {self.date}"
