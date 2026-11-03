from django.conf import settings
from django.db import models


class BadgeCriteria(models.TextChoices):
    STREAK_DAYS = "streak_days", "Current streak (days)"
    TOTAL_WORKOUTS = "total_workouts", "Total completed workouts"
    TOTAL_MEALS_LOGGED = "total_meals_logged", "Total meals logged"


class Badge(models.Model):
    """A milestone definition. Seeded data, not user-editable."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=200)
    criteria_type = models.CharField(max_length=30, choices=BadgeCriteria.choices)
    threshold = models.PositiveIntegerField()

    class Meta:
        ordering = ["criteria_type", "threshold"]

    def __str__(self):
        return self.name


class UserBadge(models.Model):
    """A badge a user has earned. Never deleted once awarded, even if the
    underlying stat later drops (e.g. a broken streak) — badges celebrate
    what a user already achieved and shouldn't be taken away.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="earned_badges")
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name="awarded_to")
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-earned_at"]
        unique_together = ("user", "badge")

    def __str__(self):
        return f"{self.user}: {self.badge.name}"


class XPEvent(models.Model):
    """One award of experience points, for an auditable, append-only total."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="xp_events")
    amount = models.PositiveIntegerField()
    reason = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user}: +{self.amount} XP ({self.reason})"


class ChallengeCriteria(models.TextChoices):
    WEEKLY_WORKOUTS = "weekly_workouts", "Completed workouts this week"
    WEEKLY_MEAL_LOG_DAYS = "weekly_meal_log_days", "Days with food logged this week"
    WEEKLY_WATER_GOAL_DAYS = "weekly_water_goal_days", "Days water goal hit this week"


class Challenge(models.Model):
    """A weekly challenge definition. Seeded data, not user-editable.

    Progress and completion are scoped to a Mon-Sun week, checked fresh
    against each week's own activity - unlike a Badge, a Challenge can be
    completed again in a later week.
    """

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=200)
    criteria_type = models.CharField(max_length=30, choices=ChallengeCriteria.choices)
    target = models.PositiveIntegerField()
    xp_reward = models.PositiveIntegerField(default=20)

    class Meta:
        ordering = ["criteria_type", "target"]

    def __str__(self):
        return self.name


class CompletedChallenge(models.Model):
    """A challenge a user finished in a specific week. One per user/challenge/week."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="completed_challenges")
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name="completions")
    week_start = models.DateField()
    xp_awarded = models.PositiveIntegerField()
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-completed_at"]
        unique_together = ("user", "challenge", "week_start")

    def __str__(self):
        return f"{self.user}: {self.challenge.name} ({self.week_start})"
