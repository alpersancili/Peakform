from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from motivation.badges import evaluate_badges

from .forms import PlanGenerateForm, RecoveryNoteForm, SetLogForm
from .generation import generate_plan_days, suggest_progression
from .models import (
    Exercise,
    ExerciseLog,
    RecoveryNote,
    SessionStatus,
    WorkoutPlan,
    WorkoutPlanDay,
    WorkoutPlanExercise,
    WorkoutSession,
)


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

        messages.success(request, "Workout complete. Nice work!")
        for note in progression_notes:
            messages.info(request, note)
        for badge in evaluate_badges(request.user):
            messages.success(request, f"New badge: {badge.name}!")

    return redirect("workouts:session_history")


@login_required
def session_history(request):
    sessions = WorkoutSession.objects.filter(user=request.user).select_related("plan_day")[:30]
    return render(request, "workouts/session_history.html", {"sessions": sessions})


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
