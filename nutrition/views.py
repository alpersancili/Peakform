from datetime import timedelta
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .calculations import calculate_bmi, calculate_daily_targets
from .forms import CustomFoodForm, MealEntryForm, StepLogForm, WaterQuickAddForm
from .models import Food, MealCategory, MealEntry, StepLog, WaterLog

WEEKLY_CHART_DAYS = 7


@login_required
def dashboard(request):
    profile = request.user.profile
    today = timezone.localdate()

    targets = calculate_daily_targets(
        weight_kg=profile.weight_kg,
        height_cm=profile.height_cm,
        age=profile.age,
        sex=profile.sex,
        activity_level=profile.activity_level,
        primary_goal=profile.primary_goal,
        override_calories=profile.calorie_target_override,
    )
    bmi = calculate_bmi(profile.weight_kg, profile.height_cm)

    todays_entries = MealEntry.objects.filter(user=request.user, logged_at__date=today).select_related("food")
    totals = todays_entries.aggregate(
        calories=Sum("calories"), protein_g=Sum("protein_g"), carbs_g=Sum("carbs_g"), fat_g=Sum("fat_g")
    )
    meals_by_category = {
        category: [e for e in todays_entries if e.meal_category == category]
        for category, _ in MealCategory.choices
    }

    water_total_ml = WaterLog.objects.filter(user=request.user, logged_at__date=today).aggregate(
        total=Sum("amount_ml")
    )["total"] or 0
    water_logs_today = WaterLog.objects.filter(user=request.user, logged_at__date=today)

    step_entry = StepLog.objects.filter(user=request.user, date=today).first()
    steps_today = step_entry.step_count if step_entry else 0

    week_start = today - timedelta(days=WEEKLY_CHART_DAYS - 1)
    week_entries = (
        MealEntry.objects.filter(user=request.user, logged_at__date__gte=week_start, logged_at__date__lte=today)
        .values_list("logged_at__date")
        .annotate(total=Sum("calories"))
    )
    calories_by_date = dict(week_entries)
    calorie_target_for_chart = targets.calories if targets else None
    weekly_chart = []
    for offset in range(WEEKLY_CHART_DAYS):
        day = week_start + timedelta(days=offset)
        day_calories = calories_by_date.get(day, 0) or 0
        pct = 0
        if calorie_target_for_chart:
            pct = min(100, round(day_calories / calorie_target_for_chart * 100))
        weekly_chart.append({"date": day, "calories": round(day_calories), "pct": pct, "is_today": day == today})

    context = {
        "profile": profile,
        "targets": targets,
        "bmi": bmi,
        "totals": totals,
        "meals_by_category": meals_by_category,
        "water_total_ml": water_total_ml,
        "water_logs_today": water_logs_today,
        "steps_today": steps_today,
        "step_form": StepLogForm(initial={"step_count": steps_today}),
        "water_form": WaterQuickAddForm(),
        "weekly_chart": weekly_chart,
    }
    return render(request, "nutrition/dashboard.html", context)


@login_required
def food_search(request):
    query = request.GET.get("q", "").strip()
    results = []
    if query:
        results = Food.objects.filter(name__icontains=query).filter(
            Q(created_by__isnull=True) | Q(created_by=request.user)
        )[:25]

    return render(
        request,
        "nutrition/food_search.html",
        {"query": query, "results": results, "meal_categories": MealCategory.choices},
    )


@login_required
def add_meal_entry(request, food_id):
    food = get_object_or_404(Food, id=food_id)
    search_url = reverse("nutrition:food_search")
    query = request.POST.get("q", "")
    back_to_search = f"{search_url}?q={quote(query)}" if query else search_url

    if request.method == "POST":
        form = MealEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user = request.user
            entry.food = food
            entry.save()
            messages.success(request, f"Logged {food.name}.")
            return redirect("nutrition:dashboard")
        messages.error(request, "Couldn't log that food. Check the quantity and try again.")
    return redirect(back_to_search)


@login_required
def custom_food_add(request):
    if request.method == "POST":
        form = CustomFoodForm(request.POST)
        if form.is_valid():
            food = form.save(commit=False)
            food.created_by = request.user
            food.save()
            messages.success(request, f"Added {food.name} to your foods.")
            return redirect(f"{reverse('nutrition:food_search')}?q={quote(food.name)}")
    else:
        form = CustomFoodForm()
    return render(request, "nutrition/custom_food_form.html", {"form": form})


@login_required
def meal_entry_edit(request, entry_id):
    entry = get_object_or_404(MealEntry, id=entry_id, user=request.user)
    if request.method == "POST":
        form = MealEntryForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            messages.success(request, "Entry updated.")
            return redirect("nutrition:dashboard")
    else:
        form = MealEntryForm(instance=entry)
    return render(request, "nutrition/meal_entry_form.html", {"form": form, "entry": entry})


@login_required
def meal_entry_delete(request, entry_id):
    entry = get_object_or_404(MealEntry, id=entry_id, user=request.user)
    if request.method == "POST":
        entry.delete()
        messages.success(request, "Entry removed.")
    return redirect("nutrition:dashboard")


@login_required
def water_add(request):
    if request.method == "POST":
        amount = request.POST.get("amount_ml")
        if amount:
            form = WaterQuickAddForm({"amount_ml": amount})
            if form.is_valid():
                WaterLog.objects.create(user=request.user, amount_ml=form.cleaned_data["amount_ml"])
        else:
            WaterLog.objects.create(user=request.user, amount_ml=request.user.profile.water_serving_ml)
    return redirect("nutrition:dashboard")


@login_required
def water_delete(request, log_id):
    log = get_object_or_404(WaterLog, id=log_id, user=request.user)
    if request.method == "POST":
        log.delete()
    return redirect("nutrition:dashboard")


@login_required
def step_set(request):
    if request.method == "POST":
        today = timezone.localdate()
        entry, _ = StepLog.objects.get_or_create(user=request.user, date=today, defaults={"step_count": 0})
        form = StepLogForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            messages.success(request, "Steps updated.")
    return redirect("nutrition:dashboard")
