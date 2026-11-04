from urllib.parse import parse_qs, urlparse

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
    CONDITIONING = "conditioning", "Conditioning"
    MOBILITY = "mobility", "Mobility"


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

    @property
    def embed_url(self):
        """The video_url converted to an iframe-embeddable YouTube URL.

        video_url is stored as an ordinary watch/share link (the form
        people actually copy and paste), but YouTube's watch page itself
        refuses to be framed - only youtube.com/embed/<id> can go in an
        <iframe>. Falls back to the stored URL unchanged if it isn't a
        YouTube link we recognize, so non-YouTube embeds aren't broken.
        """
        if not self.video_url:
            return ""
        parsed = urlparse(self.video_url)
        host = (parsed.hostname or "").removeprefix("www.").removeprefix("m.")
        video_id = None
        if host == "youtube.com" and parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        elif host == "youtu.be":
            video_id = parsed.path.lstrip("/")
        elif host == "youtube.com" and parsed.path.startswith("/embed/"):
            return self.video_url
        return f"https://www.youtube.com/embed/{video_id}" if video_id else self.video_url

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

    source_template = models.ForeignKey(
        "ProgramTemplate", null=True, blank=True, on_delete=models.SET_NULL, related_name="plans_started"
    )
    source_difficulty = models.CharField(max_length=15, blank=True)

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
            # A single long "hold" is really a practice block (e.g. 20
            # minutes of freestanding handstand attempts), not one set -
            # show it in minutes instead of "1 x 1200s hold".
            if self.target_sets == 1 and self.target_hold_seconds and self.target_hold_seconds >= 60:
                return f"{self.target_hold_seconds // 60} min practice"
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


class ProgramDifficulty(models.TextChoices):
    EASY = "easy", "Easy"
    INTERMEDIATE = "intermediate", "Intermediate"
    DIFFICULT = "difficult", "Difficult"


class ProgramTemplate(models.Model):
    """A hand-curated, named training program offered at three fixed
    difficulty tiers (e.g. "Skill-focused" / Easy, Intermediate, Difficult).

    Distinct from WorkoutPlan, which is either algorithmically generated
    (see generation.py) or cloned from one of these templates: a template
    is a fixed, reusable curriculum a user browses and "starts", which
    clones it into a real WorkoutPlan so it gets the same session
    tracking, logging, and personal records as any other plan.
    """

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    tagline = models.CharField(max_length=200, help_text="e.g. 'Master advanced skills'")
    description = models.TextField(blank=True)
    skill_rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    muscle_rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    strength_rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    athleticism_rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.name


class ProgramTemplateDay(models.Model):
    """One day (training or rest) within a template's difficulty tier."""

    template = models.ForeignKey(ProgramTemplate, on_delete=models.CASCADE, related_name="days")
    difficulty = models.CharField(max_length=15, choices=ProgramDifficulty.choices)
    day_index = models.PositiveSmallIntegerField(help_text="0-6, Monday=0")
    label = models.CharField(max_length=50)
    is_rest_day = models.BooleanField(default=False)

    class Meta:
        ordering = ["difficulty", "day_index"]
        unique_together = ("template", "difficulty", "day_index")

    def __str__(self):
        return f"{self.template.name} ({self.difficulty}) - Day {self.day_index + 1}: {self.label}"


class ProgramTemplateExercise(models.Model):
    """One exercise prescription within a ProgramTemplateDay.

    `prescription` is the exact display text (e.g. "6 x 8 sec" or
    "3 x 10") so the curated program's wording is never lost to lossy
    reinterpretation, even for odd formats like a 20-minute skill
    practice block. `target_sets`/`target_reps`/`target_hold_seconds`
    are the numeric breakdown used when this gets cloned into a real
    WorkoutPlanExercise.
    """

    day = models.ForeignKey(ProgramTemplateDay, on_delete=models.CASCADE, related_name="exercises")
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT)
    order = models.PositiveSmallIntegerField(default=0)
    prescription = models.CharField(max_length=60)
    target_sets = models.PositiveSmallIntegerField(default=3)
    target_reps = models.PositiveSmallIntegerField(null=True, blank=True)
    target_hold_seconds = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.exercise.name} ({self.prescription})"
