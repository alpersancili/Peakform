from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import WorkoutPlanAIRequest

DEFAULT_DAILY_LIMIT = 10
RATE_LIMIT_WINDOW = timedelta(days=1)


class RateLimitExceeded(Exception):
    def __init__(self, retry_after):
        self.retry_after = retry_after
        super().__init__("AI workout-plan generation rate limit exceeded.")


def _daily_limit():
    return getattr(settings, "WORKOUT_AI_DAILY_LIMIT", DEFAULT_DAILY_LIMIT)


def requests_remaining_today(user):
    window_start = timezone.now() - RATE_LIMIT_WINDOW
    used = WorkoutPlanAIRequest.objects.filter(user=user, created_at__gte=window_start).count()
    return max(0, _daily_limit() - used)


def record_attempt_or_raise(user):
    """Record an AI plan-generation attempt, raising RateLimitExceeded if over the daily cap."""
    window_start = timezone.now() - RATE_LIMIT_WINDOW
    oldest_in_window = (
        WorkoutPlanAIRequest.objects.filter(user=user, created_at__gte=window_start).order_by("created_at").first()
    )
    used = WorkoutPlanAIRequest.objects.filter(user=user, created_at__gte=window_start).count()
    if used >= _daily_limit():
        retry_after = (oldest_in_window.created_at + RATE_LIMIT_WINDOW) - timezone.now()
        raise RateLimitExceeded(retry_after)
    WorkoutPlanAIRequest.objects.create(user=user)
