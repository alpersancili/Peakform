from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .badges import evaluate_badges
from .models import Badge, UserBadge
from .streaks import calculate_current_streak, weekly_workout_progress


@login_required
def badges_list(request):
    for badge in evaluate_badges(request.user):
        messages.success(request, f"New badge: {badge.name}!")

    earned = UserBadge.objects.filter(user=request.user).select_related("badge")
    earned_badge_ids = {ub.badge_id for ub in earned}
    all_badges = Badge.objects.all()

    rows = []
    for badge in all_badges:
        user_badge = next((ub for ub in earned if ub.badge_id == badge.id), None)
        rows.append({"badge": badge, "earned": badge.id in earned_badge_ids, "earned_at": user_badge.earned_at if user_badge else None})

    context = {
        "rows": rows,
        "streak": calculate_current_streak(request.user),
        "weekly_progress": weekly_workout_progress(request.user),
    }
    return render(request, "motivation/badges_list.html", context)
