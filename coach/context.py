"""Builds the factual, real-data snapshot handed to the AI coach.

Nothing here is AI-generated: it's plain Django queries formatted as
text. The coach is instructed (see ai_client.py's system prompt) to
reason only from this data and ask the user for anything it needs that
isn't here, rather than inventing numbers - this module is what makes
that possible, by actually giving it real numbers to reason from.
"""

from django.db.models import Sum
from django.utils import timezone

from motivation.streaks import calculate_current_streak, weekly_workout_progress
from nutrition.calculations import calculate_daily_targets
from nutrition.models import MealEntry
from progress.models import ProgressEntry
from workouts.models import SessionStatus, WorkoutPlan, WorkoutSession

MAX_CONTEXT_CHARS = 3000


def build_user_context(user):
    """A compact text summary of the user's profile and recent activity."""
    profile = user.profile
    today = timezone.localdate()
    lines = [f"User: {user.username}"]

    if profile.age and profile.height_cm and profile.weight_kg:
        lines.append(
            f"Profile: {profile.age}yo, {profile.get_sex_display()}, {profile.height_cm:.0f}cm, "
            f"{profile.weight_kg:.1f}kg, activity level: {profile.get_activity_level_display()}, "
            f"experience: {profile.get_experience_level_display()}"
        )
    else:
        lines.append("Profile: incomplete (missing age/height/weight) - ask the user to fill this in "
                      "if you need it to answer their question, rather than guessing.")

    lines.append(f"Primary goal: {profile.get_primary_goal_display()}")
    if profile.equipment:
        lines.append(f"Equipment available: {', '.join(profile.equipment)}")
    else:
        lines.append("Equipment available: none listed (bodyweight only)")

    targets = calculate_daily_targets(
        weight_kg=profile.weight_kg, height_cm=profile.height_cm, age=profile.age, sex=profile.sex,
        activity_level=profile.activity_level, primary_goal=profile.primary_goal,
        override_calories=profile.calorie_target_override,
    )
    if targets:
        today_totals = MealEntry.objects.filter(user=user, logged_at__date=today).aggregate(
            calories=Sum("calories"), protein_g=Sum("protein_g"),
        )
        logged_cal = round(today_totals["calories"] or 0)
        logged_protein = round(today_totals["protein_g"] or 0)
        lines.append(
            f"Nutrition targets: {targets.calories} kcal, {targets.protein_g}g protein, "
            f"{targets.carbs_g}g carbs, {targets.fat_g}g fat per day"
        )
        lines.append(f"Logged today so far: {logged_cal} kcal, {logged_protein}g protein")
    else:
        lines.append("Nutrition targets: not available (profile is missing height/weight)")

    plan = WorkoutPlan.objects.filter(user=user, is_active=True).first()
    if plan:
        lines.append(
            f"Active workout plan: goal={plan.get_goal_display()}, "
            f"{plan.training_days_per_week} days/week, {plan.session_duration_minutes} min/session"
        )
        recent_sessions = WorkoutSession.objects.filter(
            user=user, status=SessionStatus.COMPLETED
        ).select_related("plan_day")[:5]
        if recent_sessions:
            summaries = [f"{s.date} ({s.plan_day.label if s.plan_day else 'workout'})" for s in recent_sessions]
            lines.append(f"Last completed workouts: {', '.join(summaries)}")
        else:
            lines.append("No completed workouts logged yet.")
    else:
        lines.append("No active workout plan.")

    streak = calculate_current_streak(user, today=today)
    weekly = weekly_workout_progress(user, today=today)
    lines.append(f"Current streak: {streak} days")
    lines.append(f"This week: {weekly['completed']}/{weekly['target']} planned workouts completed")

    progress_entries = list(ProgressEntry.objects.filter(user=user)[:2])
    if progress_entries:
        latest = progress_entries[0]
        lines.append(f"Latest logged weight: {latest.weight_kg}kg on {latest.date}")
        if len(progress_entries) == 2:
            change = round(progress_entries[0].weight_kg - progress_entries[-1].weight_kg, 1)
            lines.append(f"Weight change since previous log: {change:+}kg")

    return "\n".join(lines)[:MAX_CONTEXT_CHARS]
