from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from motivation.streaks import calculate_current_streak, weekly_workout_progress
from nutrition.calculations import calculate_daily_targets
from nutrition.models import MealEntry, StepLog, WaterLog
from workouts.models import ExerciseLog, SessionStatus, WorkoutSession

from .forms import ProgressEntryForm, ProgressPhotoForm
from .models import ProgressEntry, ProgressPhoto

HISTORY_DAYS = 7
CONSISTENCY_TOLERANCE = 0.15  # within 15% of the calorie target counts as "on target"
STRENGTH_TREND_WEEK_CHOICES = [8, 12, 26]  # roughly two months, three months, six months
DEFAULT_STRENGTH_TREND_WEEKS = 8


def _strength_trend(user, today, weeks):
    """Completed sets per week, oldest-first, for a simple training-volume trend.

    Grouping by week (rather than per exercise) avoids needing the user to
    pick which exercise to chart, while still showing whether training
    volume is climbing, flat, or dropping off.
    """
    current_week_start = today - timedelta(days=today.weekday())
    first_week_start = current_week_start - timedelta(weeks=weeks - 1)

    session_dates = ExerciseLog.objects.filter(
        session__user=user, session__status=SessionStatus.COMPLETED, session__date__gte=first_week_start
    ).values_list("session__date", flat=True)

    sets_by_week_start = {}
    for date in session_dates:
        week_start = date - timedelta(days=date.weekday())
        sets_by_week_start[week_start] = sets_by_week_start.get(week_start, 0) + 1

    highest = max(sets_by_week_start.values(), default=0)
    chart = []
    for offset in range(weeks):
        week_start = first_week_start + timedelta(weeks=offset)
        sets = sets_by_week_start.get(week_start, 0)
        chart.append(
            {
                "week_start": week_start,
                "sets": sets,
                "pct": round(sets / highest * 100) if highest else 0,
                "is_current": week_start == current_week_start,
            }
        )

    trend_note = None
    if weeks >= 4 and highest:
        half = weeks // 2
        earlier_avg = sum(row["sets"] for row in chart[:half]) / half
        recent_avg = sum(row["sets"] for row in chart[half:]) / (weeks - half)
        if recent_avg > earlier_avg * 1.1:
            trend_note = "Trending up — your training volume has been climbing."
        elif recent_avg < earlier_avg * 0.9:
            trend_note = "Trending down — your training volume has eased off recently."
        else:
            trend_note = "Holding steady over this period."

    return {"chart": chart, "trend_note": trend_note}


def _weight_history_chart(entries):
    """Entries oldest-first, scaled to a 0-100% bar height for the chart."""
    ordered = list(reversed(entries))
    if not ordered:
        return []
    weights = [e.weight_kg for e in ordered]
    lowest, highest = min(weights), max(weights)
    spread = highest - lowest
    chart = []
    for entry in ordered:
        pct = 100 if spread == 0 else round(10 + (entry.weight_kg - lowest) / spread * 90)
        chart.append({"date": entry.date, "weight_kg": entry.weight_kg, "pct": pct})
    return chart


def _calorie_consistency(user, today, daily_target):
    week_start = today - timedelta(days=HISTORY_DAYS - 1)
    totals = dict(
        MealEntry.objects.filter(user=user, logged_at__date__gte=week_start, logged_at__date__lte=today)
        .values_list("logged_at__date")
        .annotate(total=Sum("calories"))
    )
    logged_days = 0
    on_target_days = 0
    for offset in range(HISTORY_DAYS):
        day = week_start + timedelta(days=offset)
        day_total = totals.get(day)
        if day_total:
            logged_days += 1
            if daily_target and abs(day_total - daily_target) <= daily_target * CONSISTENCY_TOLERANCE:
                on_target_days += 1
    return {"logged_days": logged_days, "on_target_days": on_target_days, "window_days": HISTORY_DAYS}


def _activity_history(user, today, model, amount_field, date_field, goal):
    week_start = today - timedelta(days=HISTORY_DAYS - 1)
    filters = {f"{date_field}__gte": week_start, f"{date_field}__lte": today, "user": user}
    totals = dict(
        model.objects.filter(**filters).values_list(date_field).annotate(total=Sum(amount_field))
    )
    chart = []
    for offset in range(HISTORY_DAYS):
        day = week_start + timedelta(days=offset)
        amount = totals.get(day, 0) or 0
        pct = min(100, round(amount / goal * 100)) if goal else 0
        chart.append({"date": day, "amount": amount, "pct": pct, "is_today": day == today})
    return chart


@login_required
def overview(request):
    today = timezone.localdate()

    if request.method == "POST":
        form = ProgressEntryForm(request.POST)
        if form.is_valid():
            ProgressEntry.objects.update_or_create(
                user=request.user,
                date=form.cleaned_data["date"],
                defaults={
                    "weight_kg": form.cleaned_data["weight_kg"],
                    "waist_cm": form.cleaned_data["waist_cm"],
                    "chest_cm": form.cleaned_data["chest_cm"],
                    "hips_cm": form.cleaned_data["hips_cm"],
                    "arm_cm": form.cleaned_data["arm_cm"],
                    "notes": form.cleaned_data["notes"],
                },
            )
            messages.success(request, "Progress entry saved.")
            return redirect("progress:overview")
    else:
        form = ProgressEntryForm(initial={"date": today})

    entries = list(ProgressEntry.objects.filter(user=request.user)[:30])

    try:
        strength_trend_weeks = int(request.GET.get("weeks", DEFAULT_STRENGTH_TREND_WEEKS))
    except ValueError:
        strength_trend_weeks = DEFAULT_STRENGTH_TREND_WEEKS
    if strength_trend_weeks not in STRENGTH_TREND_WEEK_CHOICES:
        strength_trend_weeks = DEFAULT_STRENGTH_TREND_WEEKS

    weight_change = None
    if len(entries) >= 2:
        weight_change = round(entries[0].weight_kg - entries[-1].weight_kg, 1)

    profile = request.user.profile
    targets = calculate_daily_targets(
        weight_kg=profile.weight_kg, height_cm=profile.height_cm, age=profile.age, sex=profile.sex,
        activity_level=profile.activity_level, primary_goal=profile.primary_goal,
        override_calories=profile.calorie_target_override,
    )

    context = {
        "form": form,
        "entries": entries,
        "weight_chart": _weight_history_chart(entries[:HISTORY_DAYS]),
        "weight_change": weight_change,
        "streak": calculate_current_streak(request.user, today=today),
        "weekly_workout_progress": weekly_workout_progress(request.user, today=today),
        "total_completed_workouts": WorkoutSession.objects.filter(
            user=request.user, status=SessionStatus.COMPLETED
        ).count(),
        "calorie_consistency": _calorie_consistency(request.user, today, targets.calories if targets else None),
        "water_history": _activity_history(
            request.user, today, WaterLog, "amount_ml", "logged_at__date", profile.water_goal_ml
        ),
        "step_history": _activity_history(request.user, today, StepLog, "step_count", "date", profile.step_goal),
        "strength_trend": _strength_trend(request.user, today, strength_trend_weeks),
        "strength_trend_weeks": strength_trend_weeks,
        "strength_trend_week_choices": STRENGTH_TREND_WEEK_CHOICES,
        "recent_photos": ProgressPhoto.objects.filter(user=request.user)[:4],
        "photo_count": ProgressPhoto.objects.filter(user=request.user).count(),
    }
    return render(request, "progress/overview.html", context)


@login_required
def entry_delete(request, entry_id):
    entry = get_object_or_404(ProgressEntry, id=entry_id, user=request.user)
    if request.method == "POST":
        entry.delete()
        messages.success(request, "Entry removed.")
    return redirect("progress:overview")


@login_required
def photo_gallery(request):
    if request.method == "POST":
        form = ProgressPhotoForm(request.POST, request.FILES)
        if form.is_valid():
            photo = form.save(commit=False)
            photo.user = request.user
            photo.save()
            messages.success(request, "Progress photo uploaded.")
            return redirect("progress:photos")
    else:
        form = ProgressPhotoForm(initial={"date": timezone.localdate()})

    photos = list(ProgressPhoto.objects.filter(user=request.user))

    compare_before = compare_after = None
    before_id = request.GET.get("before")
    after_id = request.GET.get("after")
    if before_id and after_id:
        compare_before = next((p for p in photos if str(p.id) == before_id), None)
        compare_after = next((p for p in photos if str(p.id) == after_id), None)
    elif len(photos) >= 2:
        compare_before, compare_after = photos[-1], photos[0]

    context = {
        "form": form,
        "photos": photos,
        "compare_before": compare_before,
        "compare_after": compare_after,
    }
    return render(request, "progress/photos.html", context)


@login_required
def photo_delete(request, photo_id):
    photo = get_object_or_404(ProgressPhoto, id=photo_id, user=request.user)
    if request.method == "POST":
        photo.image.delete(save=False)
        photo.delete()
        messages.success(request, "Photo removed.")
    return redirect("progress:photos")
