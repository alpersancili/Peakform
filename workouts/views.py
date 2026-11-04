from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import Equipment, ExperienceLevel, PrimaryGoal
from motivation.badges import evaluate_badges
from motivation.challenges import evaluate_challenges
from motivation.xp import XP_PER_COMPLETED_WORKOUT, award_xp

from .forms import PlanGenerateForm, RecoveryNoteForm, SetLogForm
from .generation import generate_plan_days, suggest_progression
from .models import (
    Exercise,
    ExerciseLog,
    MovementCategory,
    MovementType,
    ProgramDifficulty,
    ProgramTemplate,
    RecoveryNote,
    SessionStatus,
    WorkoutPlan,
    WorkoutPlanDay,
    WorkoutPlanExercise,
    WorkoutSession,
)
from .personal_records import compute_personal_records, detect_new_records


def _active_plan(user):
    return WorkoutPlan.objects.filter(user=user, is_active=True).prefetch_related("days__exercises__exercise").first()


@login_required
def plan_generate(request):
    profile = request.user.profile
    initial = {
        "goal": profile.primary_goal,
        "experience_level": profile.experience_level,
        "training_days_per_week": profile.training_days_per_week,
        "session_duration_minutes": profile.session_duration_minutes,
        "equipment": profile.equipment,
    }

    if request.method == "POST":
        form = PlanGenerateForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            all_exercises = list(Exercise.objects.all())
            planned_days = generate_plan_days(
                all_exercises=all_exercises,
                experience_level=data["experience_level"],
                equipment=data["equipment"],
                goal=data["goal"],
                training_days_per_week=data["training_days_per_week"],
                session_duration_minutes=data["session_duration_minutes"],
            )

            WorkoutPlan.objects.filter(user=request.user, is_active=True).update(is_active=False)
            plan = WorkoutPlan.objects.create(
                user=request.user,
                goal=data["goal"],
                experience_level=data["experience_level"],
                training_days_per_week=data["training_days_per_week"],
                session_duration_minutes=data["session_duration_minutes"],
                equipment=data["equipment"],
                is_active=True,
            )
            for day in planned_days:
                plan_day = WorkoutPlanDay.objects.create(
                    plan=plan, day_index=day.day_index, label=day.label, is_rest_day=day.is_rest_day
                )
                for order, planned_exercise in enumerate(day.exercises):
                    WorkoutPlanExercise.objects.create(
                        plan_day=plan_day,
                        exercise=planned_exercise.exercise,
                        order=order,
                        target_sets=planned_exercise.target_sets,
                        target_reps=planned_exercise.target_reps,
                        target_hold_seconds=planned_exercise.target_hold_seconds,
                        rest_seconds=planned_exercise.rest_seconds,
                    )

            messages.success(request, "Your workout plan is ready.")
            return redirect("workouts:plan_overview")
    else:
        form = PlanGenerateForm(initial=initial)

    return render(request, "workouts/plan_generate.html", {"form": form})


@login_required
def plan_overview(request):
    plan = _active_plan(request.user)
    today_index = timezone.localdate().weekday()
    return render(request, "workouts/plan_overview.html", {"plan": plan, "today_index": today_index})


@login_required
def session_start(request, day_id):
    plan_day = get_object_or_404(WorkoutPlanDay, id=day_id, plan__user=request.user, plan__is_active=True)
    if plan_day.is_rest_day:
        messages.info(request, "This is a scheduled rest day.")
        return redirect("workouts:plan_overview")

    today = timezone.localdate()
    session = WorkoutSession.objects.filter(
        user=request.user, plan_day=plan_day, date=today, status=SessionStatus.IN_PROGRESS
    ).first()
    if not session:
        session = WorkoutSession.objects.create(user=request.user, plan_day=plan_day, date=today)

    return redirect("workouts:session_detail", session_id=session.id)


@login_required
def session_detail(request, session_id):
    session = get_object_or_404(
        WorkoutSession.objects.select_related("plan_day"), id=session_id, user=request.user
    )
    plan_exercises = session.plan_day.exercises.select_related("exercise") if session.plan_day else []
    logs_by_exercise = {}
    for log in session.logs.select_related("exercise"):
        logs_by_exercise.setdefault(log.exercise_id, []).append(log)

    exercise_rows = [
        {"plan_exercise": pe, "logs": logs_by_exercise.get(pe.exercise_id, [])} for pe in plan_exercises
    ]

    return render(
        request,
        "workouts/session_detail.html",
        {"session": session, "exercise_rows": exercise_rows, "set_form": SetLogForm()},
    )


@login_required
def log_set(request, session_id, exercise_id):
    session = get_object_or_404(WorkoutSession, id=session_id, user=request.user)
    exercise = get_object_or_404(Exercise, id=exercise_id)

    if request.method == "POST":
        form = SetLogForm(request.POST)
        if form.is_valid():
            set_number = session.logs.filter(exercise=exercise).count() + 1
            log = form.save(commit=False)
            log.session = session
            log.exercise = exercise
            log.set_number = set_number
            log.save()
        else:
            messages.error(request, "Couldn't log that set.")

    return redirect("workouts:session_detail", session_id=session.id)


@login_required
def session_complete(request, session_id):
    session = get_object_or_404(WorkoutSession, id=session_id, user=request.user)
    if request.method == "POST" and session.status != SessionStatus.COMPLETED:
        session.status = SessionStatus.COMPLETED
        session.completed_at = timezone.now()
        session.notes = request.POST.get("notes", "")
        session.save()

        progression_notes = []
        if session.plan_day:
            for plan_exercise in session.plan_day.exercises.select_related("exercise"):
                logs = list(session.logs.filter(exercise=plan_exercise.exercise))
                if not logs:
                    continue
                suggestion = suggest_progression(plan_exercise, logs)
                if suggestion.direction != "hold":
                    plan_exercise.target_reps = suggestion.new_target_reps
                    plan_exercise.target_hold_seconds = suggestion.new_target_hold_seconds
                    plan_exercise.save()
                    verb = "Increased" if suggestion.direction == "increase" else "Eased back"
                    progression_notes.append(f"{verb} target for {plan_exercise.exercise.name}.")

        award_xp(request.user, XP_PER_COMPLETED_WORKOUT, "Completed a workout")

        messages.success(request, "Workout complete. Nice work!")
        for exercise, value in detect_new_records(request.user, session):
            unit = "s hold" if exercise.movement_type == MovementType.HOLD else " reps"
            messages.success(request, f"New PR: {exercise.name} — {value}{unit}!")
        for note in progression_notes:
            messages.info(request, note)
        for badge in evaluate_badges(request.user):
            messages.success(request, f"New badge: {badge.name}!")
        for challenge in evaluate_challenges(request.user):
            messages.success(request, f"Challenge complete: {challenge.name} (+{challenge.xp_reward} XP)!")

    return redirect("workouts:session_history")


@login_required
def session_history(request):
    sessions = WorkoutSession.objects.filter(user=request.user).select_related("plan_day")[:30]
    return render(request, "workouts/session_history.html", {"sessions": sessions})


@login_required
def personal_records(request):
    records = compute_personal_records(request.user)
    return render(request, "workouts/personal_records.html", {"records": records})


@login_required
def recovery_note_add(request):
    today = timezone.localdate()
    note, _ = RecoveryNote.objects.get_or_create(user=request.user, date=today)

    if request.method == "POST":
        form = RecoveryNoteForm(request.POST, instance=note)
        if form.is_valid():
            form.save()
            messages.success(request, "Recovery note saved.")
            return redirect("workouts:plan_overview")
    else:
        form = RecoveryNoteForm(instance=note)

    return render(request, "workouts/recovery_note_form.html", {"form": form})


@login_required
def exercise_library(request):
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    difficulty = request.GET.get("difficulty", "")
    equipment = request.GET.get("equipment", "")

    exercises = Exercise.objects.all()
    if query:
        exercises = exercises.filter(Q(name__icontains=query) | Q(target_muscles__icontains=query))
    if category in {choice for choice, _ in MovementCategory.choices}:
        exercises = exercises.filter(category=category)
    if difficulty in {choice for choice, _ in ExperienceLevel.choices}:
        exercises = exercises.filter(difficulty_level=difficulty)
    if equipment in {choice for choice, _ in Equipment.choices}:
        # JSONField list-containment isn't portable across DB backends
        # (unsupported on SQLite), so filter in Python instead.
        exercises = [ex for ex in exercises if equipment in ex.equipment_required]

    context = {
        "exercises": exercises,
        "query": query,
        "category": category,
        "difficulty": difficulty,
        "equipment": equipment,
        "category_choices": MovementCategory.choices,
        "difficulty_choices": ExperienceLevel.choices,
        "equipment_choices": Equipment.choices,
    }
    return render(request, "workouts/exercise_library.html", context)


@login_required
def exercise_detail(request, slug):
    exercise = get_object_or_404(Exercise, slug=slug)
    personal_best = next(
        (r for r in compute_personal_records(request.user) if r["exercise"].id == exercise.id), None
    )
    return render(request, "workouts/exercise_detail.html", {"exercise": exercise, "personal_best": personal_best})


PROGRAM_DIFFICULTY_TO_EXPERIENCE = {
    ProgramDifficulty.EASY: ExperienceLevel.BEGINNER,
    ProgramDifficulty.INTERMEDIATE: ExperienceLevel.INTERMEDIATE,
    ProgramDifficulty.DIFFICULT: ExperienceLevel.ADVANCED,
}

PROGRAM_SLUG_TO_GOAL = {
    "skill-focused": PrimaryGoal.SKILLS,
    "strength-hypertrophy": PrimaryGoal.MUSCLE_GAIN,
    "mixed-training": PrimaryGoal.GENERAL_FITNESS,
}


def _recommended_difficulty(experience_level):
    return next(
        (d for d, exp in PROGRAM_DIFFICULTY_TO_EXPERIENCE.items() if exp == experience_level),
        ProgramDifficulty.INTERMEDIATE,
    )


def _recommended_slug(primary_goal):
    return next((slug for slug, goal in PROGRAM_SLUG_TO_GOAL.items() if goal == primary_goal), "mixed-training")


def _missing_equipment(user_equipment, days):
    needed = set()
    for day in days:
        for plan_exercise in day.exercises.all():
            needed.update(plan_exercise.exercise.equipment_required)
    needed.discard(Equipment.NONE)
    return sorted(needed - set(user_equipment))


@login_required
def program_list(request):
    profile = request.user.profile
    recommended_slug = _recommended_slug(profile.primary_goal)
    recommended_difficulty = _recommended_difficulty(profile.experience_level)

    templates = ProgramTemplate.objects.prefetch_related("days")
    rows = []
    for template in templates:
        rows.append(
            {
                "template": template,
                "ratings": [
                    ("Skills", template.skill_rating),
                    ("Muscle", template.muscle_rating),
                    ("Strength", template.strength_rating),
                    ("Athleticism", template.athleticism_rating),
                ],
                "is_recommended": template.slug == recommended_slug,
            }
        )
    context = {
        "rows": rows,
        "difficulty_choices": ProgramDifficulty.choices,
        "recommended_difficulty": recommended_difficulty,
    }
    return render(request, "workouts/program_list.html", context)


@login_required
def program_detail(request, slug, difficulty):
    template = get_object_or_404(ProgramTemplate, slug=slug)
    if difficulty not in {choice for choice, _ in ProgramDifficulty.choices}:
        messages.error(request, "Unknown difficulty.")
        return redirect("workouts:program_list")

    days = list(
        template.days.filter(difficulty=difficulty)
        .prefetch_related("exercises__exercise")
        .order_by("day_index")
    )
    active_plan = _active_plan(request.user)
    is_active_source = bool(
        active_plan and active_plan.source_template_id == template.id and active_plan.source_difficulty == difficulty
    )

    profile = request.user.profile
    equipment_display = dict(Equipment.choices)
    missing_equipment = [equipment_display[e] for e in _missing_equipment(profile.equipment, days)]
    is_recommended = (
        template.slug == _recommended_slug(profile.primary_goal)
        and difficulty == _recommended_difficulty(profile.experience_level)
    )

    context = {
        "template": template,
        "difficulty": difficulty,
        "difficulty_label": dict(ProgramDifficulty.choices)[difficulty],
        "difficulty_choices": ProgramDifficulty.choices,
        "days": days,
        "is_active_source": is_active_source,
        "missing_equipment": missing_equipment,
        "is_recommended": is_recommended,
        "training_days_per_week": sum(1 for day in days if not day.is_rest_day),
    }
    return render(request, "workouts/program_detail.html", context)


@login_required
def program_start(request, slug, difficulty):
    template = get_object_or_404(ProgramTemplate, slug=slug)
    if difficulty not in {choice for choice, _ in ProgramDifficulty.choices}:
        messages.error(request, "Unknown difficulty.")
        return redirect("workouts:program_list")

    if request.method != "POST":
        return redirect("workouts:program_detail", slug=slug, difficulty=difficulty)

    source_days = (
        template.days.filter(difficulty=difficulty).prefetch_related("exercises__exercise").order_by("day_index")
    )
    training_days = sum(1 for day in source_days if not day.is_rest_day)

    WorkoutPlan.objects.filter(user=request.user, is_active=True).update(is_active=False)
    plan = WorkoutPlan.objects.create(
        user=request.user,
        goal=PROGRAM_SLUG_TO_GOAL.get(template.slug, PrimaryGoal.GENERAL_FITNESS),
        experience_level=PROGRAM_DIFFICULTY_TO_EXPERIENCE[difficulty],
        training_days_per_week=training_days,
        session_duration_minutes=60,
        equipment=request.user.profile.equipment,
        source_template=template,
        source_difficulty=difficulty,
        is_active=True,
    )
    for source_day in source_days:
        plan_day = WorkoutPlanDay.objects.create(
            plan=plan, day_index=source_day.day_index, label=source_day.label, is_rest_day=source_day.is_rest_day
        )
        for source_exercise in source_day.exercises.all():
            rest_seconds = 150 if source_exercise.exercise.movement_type == MovementType.HOLD else 120
            WorkoutPlanExercise.objects.create(
                plan_day=plan_day,
                exercise=source_exercise.exercise,
                order=source_exercise.order,
                target_sets=source_exercise.target_sets,
                target_reps=source_exercise.target_reps,
                target_hold_seconds=source_exercise.target_hold_seconds,
                rest_seconds=rest_seconds,
            )

    messages.success(request, f"Started {template.name} ({dict(ProgramDifficulty.choices)[difficulty]}).")
    return redirect("workouts:plan_overview")
