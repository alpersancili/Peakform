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

# Day-label -> movement categories drawn from, by split type. Push and
# Pull are never combined into one session except inside "Upper Body"
# (used only at 2 and 4 days/week, where there isn't enough frequency
# to dedicate a whole day to each and still train legs) - 3+ days/week
# always get a dedicated Push day and a dedicated Pull day, matching
# how real calisthenics push/pull/legs programming is actually
# structured. "Legs" always means legs AND core/abs together (a static
# hold like an L-sit pairs naturally with a leg day), never push or
# pull.
#
# The split structure itself - not just the prescription inside it -
# depends on the goal: Skills gets a dedicated Push/Pull split from the
# lowest day counts (skill work needs its own focused sessions);
# Strength/Muscle gain/General fitness use Full Body at low frequency
# and split into Upper/Lower (then Push/Pull/Legs) as frequency allows;
# Fat loss alternates full-body strength with short conditioning blocks;
# Endurance and Flexibility are their own session types entirely
# (Conditioning / Mobility), not variations on a push/pull/legs split -
# a user who picks "Endurance" should get aerobic/circuit work, not a
# strength split with shorter rest.
SPLIT_BY_GOAL_AND_DAYS = {
    PrimaryGoal.SKILLS: {
        1: ["Full Body"],
        2: ["Push", "Pull"],
        3: ["Push", "Pull", "Legs"],
        4: ["Push", "Pull", "Push", "Pull"],
        5: ["Push", "Pull", "Legs", "Push", "Pull"],
        6: ["Push", "Pull", "Legs", "Push", "Pull", "Legs"],
    },
    PrimaryGoal.STRENGTH: {
        1: ["Full Body"],
        2: ["Full Body", "Full Body"],
        3: ["Full Body", "Full Body", "Full Body"],
        4: ["Upper Body", "Lower Body", "Upper Body", "Lower Body"],
        5: ["Upper Body", "Lower Body", "Upper Body", "Lower Body", "Full Body"],
        6: ["Upper Body", "Lower Body", "Full Body", "Upper Body", "Lower Body", "Full Body"],
    },
    PrimaryGoal.MUSCLE_GAIN: {
        1: ["Full Body"],
        2: ["Full Body", "Full Body"],
        3: ["Full Body", "Full Body", "Full Body"],
        4: ["Upper Body", "Lower Body", "Upper Body", "Lower Body"],
        5: ["Push", "Pull", "Legs", "Upper Body", "Lower Body"],
        6: ["Push", "Pull", "Legs", "Push", "Pull", "Legs"],
    },
    PrimaryGoal.FAT_LOSS: {
        1: ["Full Body"],
        2: ["Full Body", "Full Body"],
        3: ["Full Body", "Conditioning", "Full Body"],
        4: ["Full Body", "Conditioning", "Full Body", "Conditioning"],
        5: ["Full Body", "Conditioning", "Full Body", "Conditioning", "Full Body"],
        6: ["Full Body", "Conditioning", "Full Body", "Conditioning", "Full Body", "Conditioning"],
    },
    PrimaryGoal.GENERAL_FITNESS: {
        1: ["Full Body"],
        2: ["Full Body", "Full Body"],
        3: ["Full Body", "Full Body", "Full Body"],
        4: ["Upper Body", "Lower Body", "Full Body", "Conditioning"],
        5: ["Upper Body", "Lower Body", "Conditioning", "Upper Body", "Lower Body"],
        6: ["Upper Body", "Lower Body", "Conditioning", "Upper Body", "Lower Body", "Full Body"],
    },
    PrimaryGoal.ENDURANCE: {n: ["Conditioning"] * n for n in range(1, 7)},
    PrimaryGoal.FLEXIBILITY: {n: ["Mobility"] * n for n in range(1, 7)},
}

# Which of the 7 day_index slots (0=first day of the cycle) are training
# days, by training_days_per_week. Spread across the week rather than
# clustered at the start, so the same muscle groups always get at least
# a day of recovery before being trained again - three Full Body days
# back-to-back-to-back with four rest days afterward is worse recovery
# management than the same three days spread out, even though both use
# "3 training days." 6 days/week is already a standard Mon-Sat pattern
# and doesn't need spreading.
TRAINING_DAY_INDICES = {
    1: [0],
    2: [0, 3],  # Mon, Thu
    3: [0, 2, 4],  # Mon, Wed, Fri
    4: [0, 1, 3, 4],  # Mon, Tue, Thu, Fri - a day of rest after each 2-day block
    5: [0, 1, 3, 4, 5],  # Mon, Tue, Thu, Fri, Sat - rest mid-week and Sunday
    6: [0, 1, 2, 3, 4, 5],
}

# Skill-category exercises (static holds like handstand/planche
# progressions) are all push/pressing-dominant in this library - the
# pull-dominant equivalents (front lever family) are already their own
# "pull" category exercises and so only ever appear on pull days
# naturally. Only add the skill category to push-type days, so a
# planche progression can never land on a pull or legs day.
SKILLS_GOAL_LABELS = {"Push", "Upper Body", "Full Body"}

# How each goal actually changes the prescription for main-block exercises
# (never warm-up/cool-down, which stay standardized). Multipliers on the
# exercise's own baseline sets/reps/hold/rest - not arbitrary numbers, but
# a real coaching distinction: strength work is low-rep/near-max-effort
# with long rest for full ATP-CP recovery between sets; endurance work is
# high-rep with short rest for metabolic conditioning; skill work (e.g.
# handstand, planche, front lever progressions) needs long rest between
# attempts because quality and full neurological freshness matter far
# more than fatiguing through volume - a tired nervous system reinforces
# bad technique and skill practice done fatigued barely transfers. Before
# this, every goal produced an identical prescription for the same
# exercise, which is not what a program "for strength" vs "for
# endurance" actually looks like in practice.
GOAL_PROGRAMMING = {
    PrimaryGoal.STRENGTH: {"rep_mult": 0.6, "hold_mult": 0.7, "rest_mult": 1.6, "sets_delta": 1},
    PrimaryGoal.ENDURANCE: {"rep_mult": 1.6, "hold_mult": 1.5, "rest_mult": 0.6, "sets_delta": 0},
    PrimaryGoal.MUSCLE_GAIN: {"rep_mult": 1.1, "hold_mult": 1.0, "rest_mult": 0.9, "sets_delta": 1},
    PrimaryGoal.FAT_LOSS: {"rep_mult": 1.3, "hold_mult": 1.1, "rest_mult": 0.65, "sets_delta": 0},
    PrimaryGoal.SKILLS: {"rep_mult": 0.9, "hold_mult": 1.0, "rest_mult": 1.4, "sets_delta": 0},
    PrimaryGoal.FLEXIBILITY: {"rep_mult": 1.0, "hold_mult": 1.6, "rest_mult": 0.8, "sets_delta": 0},
    PrimaryGoal.GENERAL_FITNESS: {"rep_mult": 1.0, "hold_mult": 1.0, "rest_mult": 1.0, "sets_delta": 0},
}
MIN_TARGET_REPS = 3
MAX_TARGET_REPS = 50
MIN_TARGET_HOLD_SECONDS = 5
MAX_TARGET_HOLD_SECONDS = 180
MIN_REST_SECONDS = 15
MAX_REST_SECONDS = 240
MIN_SETS = 1
MAX_SETS = 6

LABEL_CATEGORIES = {
    "Full Body": [MovementCategory.PUSH, MovementCategory.PULL, MovementCategory.LEGS, MovementCategory.CORE],
    "Upper Body": [MovementCategory.PUSH, MovementCategory.PULL, MovementCategory.CORE],
    "Lower Body": [MovementCategory.LEGS, MovementCategory.CORE],
    # Push days stay pure push work (plus push-dominant skill holds, see
    # SKILLS_GOAL_LABELS below) - no core filler mixed in, matching how
    # a dedicated push day is actually programmed.
    "Push": [MovementCategory.PUSH],
    # Pull days commonly pair naturally with hanging ab/core work
    # (hanging leg raises etc. use the same bar), so core stays here.
    "Pull": [MovementCategory.PULL, MovementCategory.CORE],
    "Legs": [MovementCategory.LEGS, MovementCategory.CORE],
    "Conditioning": [MovementCategory.CONDITIONING],
    "Mobility": [MovementCategory.MOBILITY],
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


def _exercises_per_day(session_duration_minutes, goal=None):
    """How many main exercises fit in the session, given how goal scaling
    changes time-per-exercise. A strength day's 1.6x rest and +1 set take
    meaningfully longer per exercise than an endurance day's 0.6x rest -
    without accounting for that, a "60-minute" strength session packed
    with as many exercises as an endurance session would actually run
    well over two hours of real rest time alone.
    """
    scale = GOAL_PROGRAMMING.get(goal) if goal else None
    time_multiplier = scale["rest_mult"] * (3 + scale["sets_delta"]) / 3 if scale else 1.0

    working_minutes = max(0, session_duration_minutes - 10)  # reserve ~10 min for warm-up/cool-down
    count = round(working_minutes / (MINUTES_PER_EXERCISE * time_multiplier))
    return max(MIN_EXERCISES_PER_DAY, min(MAX_EXERCISES_PER_DAY, count))


def _to_planned_exercise(exercise, goal=None):
    """Build a PlannedExercise, scaling the exercise's baseline prescription
    for the user's goal. `goal=None` (used for warm-up/cool-down) keeps the
    exercise's own defaults unscaled - a goal shouldn't change how long you
    stretch your quads.
    """
    scale = GOAL_PROGRAMMING.get(goal) if goal else None

    sets = exercise.default_sets
    reps = exercise.default_reps if exercise.movement_type == MovementType.REPS else None
    hold = exercise.default_hold_seconds if exercise.movement_type == MovementType.HOLD else None
    rest = exercise.default_rest_seconds

    if scale:
        sets = max(MIN_SETS, min(MAX_SETS, sets + scale["sets_delta"]))
        if reps is not None:
            reps = max(MIN_TARGET_REPS, min(MAX_TARGET_REPS, round(reps * scale["rep_mult"])))
        if hold is not None:
            hold = max(MIN_TARGET_HOLD_SECONDS, min(MAX_TARGET_HOLD_SECONDS, round(hold * scale["hold_mult"])))
        rest = max(MIN_REST_SECONDS, min(MAX_REST_SECONDS, round(rest * scale["rest_mult"])))

    return PlannedExercise(exercise=exercise, target_sets=sets, target_reps=reps, target_hold_seconds=hold, rest_seconds=rest)


def generate_plan_days(all_exercises, experience_level, equipment, goal, training_days_per_week, session_duration_minutes):
    """Build a 7-day plan cycle. Returns a list of 7 PlannedDay objects.

    `all_exercises` should be a list/queryset of Exercise instances
    (passed in so callers can prefetch once and tests can use fixtures).
    """
    training_days = max(1, min(training_days_per_week, MAX_TRAINING_DAYS))
    goal_splits = SPLIT_BY_GOAL_AND_DAYS.get(goal, SPLIT_BY_GOAL_AND_DAYS[PrimaryGoal.GENERAL_FITNESS])
    split = goal_splits[training_days]
    training_indices = TRAINING_DAY_INDICES[training_days]
    exercises_per_day = _exercises_per_day(session_duration_minutes, goal=goal)

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
        if day_index not in training_indices:
            days.append(PlannedDay(day_index=day_index, label="Rest", is_rest_day=True))
            continue

        split_position = training_indices.index(day_index)
        label = split[split_position]
        categories = LABEL_CATEGORIES[label]
        if goal == PrimaryGoal.SKILLS and label in SKILLS_GOAL_LABELS:
            categories = categories + [MovementCategory.SKILL]
        candidates = _exercises_for_category(all_exercises, categories, experience_level, equipment, goal)

        # Rotate the starting point per occurrence of this label so repeated
        # split days (e.g. Push appearing twice in a 6-day split) don't get
        # an identical exercise list.
        offset = (split_position * 3) % max(1, len(candidates))
        rotated = candidates[offset:] + candidates[:offset]
        selected = rotated[:exercises_per_day]
        # Skill work (handstands, planche/front lever progressions) goes
        # first among the main exercises, while the nervous system is
        # still fresh from the warm-up - fatigued skill practice mostly
        # just reinforces bad form rather than building the skill. This
        # covers both the "skill" category itself (handstand/planche,
        # which are push-dominant) and any exercise explicitly tagged
        # for the skills goal regardless of its push/pull/legs/core
        # category (front lever progressions are catalogued as "pull"
        # since they're also valid pure pulling-strength work, but are
        # just as much a skill that deserves to come first when fresh).
        def _skill_priority(ex):
            is_skill_work = ex.category == MovementCategory.SKILL or PrimaryGoal.SKILLS in ex.primary_goal_tags
            return 0 if is_skill_work else 1

        selected = sorted(selected, key=_skill_priority)

        planned_day = PlannedDay(day_index=day_index, label=label, is_rest_day=False)
        for warmup_ex in warmup_pool[:WARMUP_EXERCISE_COUNT]:
            planned_day.exercises.append(_to_planned_exercise(warmup_ex))
        for ex in selected:
            planned_day.exercises.append(_to_planned_exercise(ex, goal=goal))
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
