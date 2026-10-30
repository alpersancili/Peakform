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
