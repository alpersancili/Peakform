"""Deterministic workout plan generation and progression rules.

No AI is used here by design: workout structure, equipment/experience
filtering, and progression are explicit, testable application logic (per
the product brief). An AI assistant may later help personalize copy or
suggestions, but the underlying plan structure stays rule-based.
"""

from dataclasses import dataclass, field

from accounts.models import ExperienceLevel, PrimaryGoal

from .models import Exercise, MovementCategory, MovementType

MAX_TRAINING_DAYS = 6  # at least one rest day per 7-day cycle, always.
MIN_EXERCISES_PER_DAY = 3
MAX_EXERCISES_PER_DAY = 8
MINUTES_PER_EXERCISE = 6  # rough estimate: sets x (work + rest)
WARMUP_EXERCISE_COUNT = 2
COOLDOWN_EXERCISE_COUNT = 1

# Day-label -> movement categories drawn from, by split type.
SPLIT_BY_DAY_COUNT = {
    1: ["Full Body"],
    2: ["Full Body", "Full Body"],
    3: ["Full Body", "Full Body", "Full Body"],
    4: ["Upper Body", "Lower Body", "Upper Body", "Lower Body"],
    5: ["Push", "Pull", "Legs", "Upper Body", "Lower Body"],
    6: ["Push", "Pull", "Legs", "Push", "Pull", "Legs"],
}

LABEL_CATEGORIES = {
    "Full Body": [MovementCategory.PUSH, MovementCategory.PULL, MovementCategory.LEGS, MovementCategory.CORE],
    "Upper Body": [MovementCategory.PUSH, MovementCategory.PULL, MovementCategory.CORE],
    "Lower Body": [MovementCategory.LEGS, MovementCategory.CORE],
    "Push": [MovementCategory.PUSH, MovementCategory.CORE],
    "Pull": [MovementCategory.PULL, MovementCategory.CORE],
    "Legs": [MovementCategory.LEGS],
}


@dataclass
class PlannedExercise:
    exercise: Exercise
    target_sets: int
    target_reps: int | None
    target_hold_seconds: int | None
    rest_seconds: int


@dataclass
class PlannedDay:
    day_index: int
    label: str
    is_rest_day: bool
    exercises: list[PlannedExercise] = field(default_factory=list)


def _exercises_for_category(all_exercises, categories, experience_level, equipment, goal):
    candidates = [
        ex
        for ex in all_exercises
        if ex.category in categories and ex.suits_experience(experience_level) and ex.suits_equipment(equipment)
    ]
    goal_matches = [ex for ex in candidates if goal in ex.primary_goal_tags]
    goal_agnostic = [ex for ex in candidates if ex not in goal_matches]
    # Stable ordering (by id) within each group keeps generation deterministic.
    return sorted(goal_matches, key=lambda e: e.id) + sorted(goal_agnostic, key=lambda e: e.id)


def _exercises_per_day(session_duration_minutes):
    working_minutes = max(0, session_duration_minutes - 10)  # reserve ~10 min for warm-up/cool-down
    count = round(working_minutes / MINUTES_PER_EXERCISE)
    return max(MIN_EXERCISES_PER_DAY, min(MAX_EXERCISES_PER_DAY, count))


def _to_planned_exercise(exercise):
    return PlannedExercise(
        exercise=exercise,
        target_sets=exercise.default_sets,
        target_reps=exercise.default_reps if exercise.movement_type == MovementType.REPS else None,
        target_hold_seconds=exercise.default_hold_seconds if exercise.movement_type == MovementType.HOLD else None,
        rest_seconds=exercise.default_rest_seconds,
    )


def generate_plan_days(all_exercises, experience_level, equipment, goal, training_days_per_week, session_duration_minutes):
    """Build a 7-day plan cycle. Returns a list of 7 PlannedDay objects.

    `all_exercises` should be a list/queryset of Exercise instances
    (passed in so callers can prefetch once and tests can use fixtures).
    """
    training_days = max(1, min(training_days_per_week, MAX_TRAINING_DAYS))
    split = SPLIT_BY_DAY_COUNT[training_days]
    exercises_per_day = _exercises_per_day(session_duration_minutes)

    warmup_pool = sorted(
        [ex for ex in all_exercises if ex.category == MovementCategory.WARMUP and ex.suits_equipment(equipment)],
        key=lambda e: e.id,
    )
    cooldown_pool = sorted(
        [ex for ex in all_exercises if ex.category == MovementCategory.COOLDOWN and ex.suits_equipment(equipment)],
        key=lambda e: e.id,
    )

    days = []
    for day_index in range(7):
        if day_index >= len(split):
            days.append(PlannedDay(day_index=day_index, label="Rest", is_rest_day=True))
            continue

        label = split[day_index]
        categories = LABEL_CATEGORIES[label]
        if goal == PrimaryGoal.SKILLS:
            categories = categories + [MovementCategory.SKILL]
        candidates = _exercises_for_category(all_exercises, categories, experience_level, equipment, goal)

        # Rotate the starting point per occurrence of this label so repeated
        # split days (e.g. Push appearing twice in a 6-day split) don't get
        # an identical exercise list.
        offset = (day_index * 3) % max(1, len(candidates))
        rotated = candidates[offset:] + candidates[:offset]
        selected = rotated[:exercises_per_day]

        planned_day = PlannedDay(day_index=day_index, label=label, is_rest_day=False)
        for i, warmup_ex in enumerate(warmup_pool[:WARMUP_EXERCISE_COUNT]):
            planned_day.exercises.append(_to_planned_exercise(warmup_ex))
        for ex in selected:
            planned_day.exercises.append(_to_planned_exercise(ex))
        for ex in cooldown_pool[:COOLDOWN_EXERCISE_COUNT]:
            planned_day.exercises.append(_to_planned_exercise(ex))

        days.append(planned_day)

    return days


# ---------------------------------------------------------------------------
# Progression
# ---------------------------------------------------------------------------

RPE_TOO_EASY = 6  # at or below this, and hitting target, suggests increasing difficulty
RPE_TOO_HARD = 9  # at or above this suggests easing off next time
REPS_INCREMENT = 1
HOLD_INCREMENT_SECONDS = 5


@dataclass
class ProgressionSuggestion:
    new_target_reps: int | None
    new_target_hold_seconds: int | None
    direction: str  # "increase", "decrease", or "hold"


def suggest_progression(plan_exercise, session_logs):
    """Suggest a new target for a plan exercise based on how a session went.

    Rule-based, not AI: if every logged set met or beat the target and
    perceived effort was moderate (not maxed out), nudge the target up.
    If effort was very high, ease back slightly for safety. Otherwise,
    keep the same target. Sessions with no effort data default to holding
    the same target rather than guessing.
    """
    if not session_logs:
        return ProgressionSuggestion(
            new_target_reps=plan_exercise.target_reps,
            new_target_hold_seconds=plan_exercise.target_hold_seconds,
            direction="hold",
        )

    is_hold = plan_exercise.exercise.movement_type == MovementType.HOLD
    target = plan_exercise.target_hold_seconds if is_hold else plan_exercise.target_reps

    met_target = all(
        (log.hold_seconds or 0) >= (target or 0) if is_hold else (log.reps or 0) >= (target or 0)
        for log in session_logs
    )
    rpe_values = [log.effort_rpe for log in session_logs if log.effort_rpe is not None]
    avg_rpe = sum(rpe_values) / len(rpe_values) if rpe_values else None

    direction = "hold"
    if avg_rpe is not None and avg_rpe >= RPE_TOO_HARD:
        direction = "decrease"
    elif met_target and (avg_rpe is None or avg_rpe <= RPE_TOO_EASY):
        direction = "increase"

    new_reps, new_hold = plan_exercise.target_reps, plan_exercise.target_hold_seconds
    if direction == "increase":
        if is_hold:
            new_hold = (new_hold or 0) + HOLD_INCREMENT_SECONDS
        else:
            new_reps = (new_reps or 0) + REPS_INCREMENT
    elif direction == "decrease":
        if is_hold:
            new_hold = max(5, (new_hold or HOLD_INCREMENT_SECONDS) - HOLD_INCREMENT_SECONDS)
        else:
            new_reps = max(1, (new_reps or REPS_INCREMENT) - REPS_INCREMENT)

    return ProgressionSuggestion(new_target_reps=new_reps, new_target_hold_seconds=new_hold, direction=direction)
