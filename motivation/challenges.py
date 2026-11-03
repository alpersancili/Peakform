"""Weekly challenge evaluation: explicit, rule-based criteria checked
against a user's current week (Mon-Sun), mirroring badges.py but scoped
to a week instead of all-time so a challenge can be completed again
later.
"""

from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from .models import Challenge, ChallengeCriteria, CompletedChallenge
from .xp import award_xp


def _weekly_workouts(user, week_start, week_end):
    from workouts.models import SessionStatus, WorkoutSession

    return WorkoutSession.objects.filter(
        user=user, status=SessionStatus.COMPLETED, date__gte=week_start, date__lte=week_end
    ).count()


def _weekly_meal_log_days(user, week_start, week_end):
    from nutrition.models import MealEntry

    return (
        MealEntry.objects.filter(user=user, logged_at__date__gte=week_start, logged_at__date__lte=week_end)
        .dates("logged_at", "day")
        .count()
    )


def _weekly_water_goal_days(user, week_start, week_end):
    from nutrition.models import WaterLog

    goal = user.profile.water_goal_ml
    if not goal:
        return 0
    daily_totals = (
        WaterLog.objects.filter(user=user, logged_at__date__gte=week_start, logged_at__date__lte=week_end)
        .values_list("logged_at__date")
        .annotate(total=Sum("amount_ml"))
    )
    return sum(1 for _, total in daily_totals if total >= goal)


CRITERIA_CALCULATORS = {
    ChallengeCriteria.WEEKLY_WORKOUTS: _weekly_workouts,
    ChallengeCriteria.WEEKLY_MEAL_LOG_DAYS: _weekly_meal_log_days,
    ChallengeCriteria.WEEKLY_WATER_GOAL_DAYS: _weekly_water_goal_days,
}


def current_week_bounds(today=None):
    today = today or timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def challenge_progress(user, today=None):
    """This week's progress on every challenge, for display."""
    week_start, week_end = current_week_bounds(today)
    completed_slugs = set(
        CompletedChallenge.objects.filter(user=user, week_start=week_start).values_list(
            "challenge__slug", flat=True
        )
    )

    rows = []
    for challenge in Challenge.objects.all():
        calculator = CRITERIA_CALCULATORS.get(challenge.criteria_type)
        current = calculator(user, week_start, week_end) if calculator else 0
        rows.append(
            {
                "challenge": challenge,
                "current": min(current, challenge.target),
                "target": challenge.target,
                "completed": challenge.slug in completed_slugs,
            }
        )
    return rows


def evaluate_challenges(user, today=None):
    """Record and award XP for any newly-finished challenges this week. Returns the list just completed."""
    week_start, week_end = current_week_bounds(today)
    already_completed_ids = set(
        CompletedChallenge.objects.filter(user=user, week_start=week_start).values_list("challenge_id", flat=True)
    )

    newly_completed = []
    for challenge in Challenge.objects.exclude(id__in=already_completed_ids):
        calculator = CRITERIA_CALCULATORS.get(challenge.criteria_type)
        if calculator is None:
            continue
        if calculator(user, week_start, week_end) >= challenge.target:
            CompletedChallenge.objects.create(
                user=user, challenge=challenge, week_start=week_start, xp_awarded=challenge.xp_reward
            )
            award_xp(user, challenge.xp_reward, f"Challenge: {challenge.name}")
            newly_completed.append(challenge)
    return newly_completed
