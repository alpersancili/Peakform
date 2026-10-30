"""Badge evaluation: explicit, rule-based criteria checked against a
user's current stats. Not AI-driven — milestones should be predictable
and reproducible.
"""

from .models import Badge, BadgeCriteria, UserBadge
from .streaks import calculate_current_streak


def _total_workouts(user):
    from workouts.models import SessionStatus, WorkoutSession

    return WorkoutSession.objects.filter(user=user, status=SessionStatus.COMPLETED).count()


def _total_meals_logged(user):
    from nutrition.models import MealEntry

    return MealEntry.objects.filter(user=user).count()


CRITERIA_CALCULATORS = {
    BadgeCriteria.STREAK_DAYS: calculate_current_streak,
    BadgeCriteria.TOTAL_WORKOUTS: _total_workouts,
    BadgeCriteria.TOTAL_MEALS_LOGGED: _total_meals_logged,
}


def evaluate_badges(user):
    """Award any newly-qualified badges and return the list just earned."""
    already_earned_ids = set(UserBadge.objects.filter(user=user).values_list("badge_id", flat=True))
    stat_cache = {}
    newly_earned = []

    for badge in Badge.objects.exclude(id__in=already_earned_ids):
        calculator = CRITERIA_CALCULATORS.get(badge.criteria_type)
        if calculator is None:
            continue
        if badge.criteria_type not in stat_cache:
            stat_cache[badge.criteria_type] = calculator(user)
        if stat_cache[badge.criteria_type] >= badge.threshold:
            UserBadge.objects.create(user=user, badge=badge)
            newly_earned.append(badge)

    return newly_earned
