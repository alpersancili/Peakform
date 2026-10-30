"""Streak calculation: deterministic, rest-day aware, and never punitive.

A streak counts consecutive days of "meaningful" activity (a completed
workout or at least one logged meal), walking backward from today. A
day scheduled as a rest day on the user's active plan always counts as
maintained, whether or not anything was logged — planned rest is part of
the plan, not a lapse. Today itself is never the reason a streak breaks:
if today has no activity yet, we simply don't count it and keep looking
at prior days, since the day isn't over.
"""

from datetime import timedelta

from django.utils import timezone

MAX_LOOKBACK_DAYS = 400


def _rest_weekdays_for_active_plan(user):
    from workouts.models import WorkoutPlan

    plan = WorkoutPlan.objects.filter(user=user, is_active=True).prefetch_related("days").first()
    if not plan:
        return set()
    return {day.day_index for day in plan.days.all() if day.is_rest_day}


def has_activity_on(user, date):
    """True if the user completed a workout or logged a meal on this date."""
    from nutrition.models import MealEntry
    from workouts.models import SessionStatus, WorkoutSession

    if WorkoutSession.objects.filter(user=user, date=date, status=SessionStatus.COMPLETED).exists():
        return True
    return MealEntry.objects.filter(user=user, logged_at__date=date).exists()


def calculate_current_streak(user, today=None):
    """Consecutive days of activity (or scheduled rest) ending today."""
    today = today or timezone.localdate()
    rest_weekdays = _rest_weekdays_for_active_plan(user)

    streak = 0
    current_date = today
    for _ in range(MAX_LOOKBACK_DAYS):
        if current_date.weekday() in rest_weekdays:
            current_date -= timedelta(days=1)
            continue

        if has_activity_on(user, current_date):
            streak += 1
            current_date -= timedelta(days=1)
            continue

        if current_date == today:
            current_date -= timedelta(days=1)
            continue

        break

    return streak


def weekly_workout_progress(user, today=None):
    """Completed-vs-target workout count for the current Mon-Sun week.

    The target is the active plan's training_days_per_week; there's
    nothing to track without an active plan.
    """
    from workouts.models import SessionStatus, WorkoutPlan, WorkoutSession

    today = today or timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    plan = WorkoutPlan.objects.filter(user=user, is_active=True).first()
    target = plan.training_days_per_week if plan else 0

    completed = WorkoutSession.objects.filter(
        user=user, status=SessionStatus.COMPLETED, date__gte=week_start, date__lte=week_end
    ).count()

    return {"completed": completed, "target": target, "week_start": week_start, "week_end": week_end}
