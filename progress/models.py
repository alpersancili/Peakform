from django.conf import settings
from django.db import models
from django.utils import timezone


class ProgressEntry(models.Model):
    """A user-logged body-weight and optional measurements snapshot.

    One entry per user per day - re-logging the same day updates that
    day's entry rather than creating a duplicate (mirrors the StepLog
    pattern elsewhere), so a weight history isn't skewed by same-day
    corrections.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="progress_entries")
    date = models.DateField(default=timezone.localdate)
    weight_kg = models.FloatField()
    waist_cm = models.FloatField(null=True, blank=True)
    chest_cm = models.FloatField(null=True, blank=True)
    hips_cm = models.FloatField(null=True, blank=True)
    arm_cm = models.FloatField(null=True, blank=True)
    notes = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]
        unique_together = ("user", "date")
        verbose_name_plural = "progress entries"

    def __str__(self):
        return f"{self.user}: {self.weight_kg}kg on {self.date}"
