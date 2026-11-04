"""AI-assisted workout plan generation via the Google Gemini API.

Gemini is given the user's goal/experience/equipment/availability plus
the exact set of catalog exercises that already pass equipment and
experience filtering, and asked to design a full 7-day training cycle
from them - which days train what, in what order, with what sets/reps/
holds/rest. It can only reference exercises by id from the list it was
given; nothing it returns is trusted until every id, count, and day
structure is validated against that same list and the user's own
training_days_per_week. Warm-up and cool-down stay fully deterministic
(see generation.warmup_cooldown_pools) - there's no reason to spend a
model call choosing between two arm-circle variants.

If the API is unreachable, unconfigured, or returns something that
doesn't validate, the caller falls back to the deterministic rule-based
generator in generation.py - plan generation must never fail outright.
"""

import json
import urllib.error
import urllib.request

from django.conf import settings

from accounts.models import Equipment, ExperienceLevel, PrimaryGoal

from .generation import (
    COOLDOWN_EXERCISE_COUNT,
    MAX_EXERCISES_PER_DAY,
    MAX_REST_SECONDS,
    MAX_SETS,
    MAX_TARGET_HOLD_SECONDS,
    MAX_TARGET_REPS,
    MAX_TRAINING_DAYS,
    MIN_EXERCISES_PER_DAY,
    MIN_REST_SECONDS,
    MIN_SETS,
    MIN_TARGET_HOLD_SECONDS,
    MIN_TARGET_REPS,
    MINUTES_PER_EXERCISE,
    WARMUP_EXERCISE_COUNT,
    PlannedDay,
    PlannedExercise,
    _to_planned_exercise,
    warmup_cooldown_pools,
)
from .models import MovementCategory, MovementType

GEMINI_ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)
REQUEST_TIMEOUT_SECONDS = 30  # a full weekly plan is a much bigger completion than a single food item

GOAL_GUIDANCE = {
    "skills": (
        "Prioritize skill practice (planche, front lever, handstand, muscle-up, L-sit progressions) "
        "early in each session while the nervous system is fresh. Use a dedicated Push day and a "
        "dedicated Pull day from 2 days/week onward; add a Legs day once there are 3+ days/week. "
        "Use low reps (3-8) or short holds (5-15 sec) with long rest (90-150 sec) for skill work."
    ),
    "strength": (
        "Use full-body sessions at low weekly frequency, splitting into Upper Body/Lower Body (or "
        "Push/Pull/Legs) only as days/week increases. Prescribe low reps (3-8) with long rest "
        "(120-180 sec) on the main compound movements."
    ),
    "muscle_gain": (
        "Use full-body sessions at low weekly frequency, splitting by Push/Pull/Legs or Upper/Lower "
        "as days/week increases, training each movement pattern about twice a week. Prescribe "
        "moderate reps (6-15) with moderate rest (60-120 sec)."
    ),
    "fat_loss": (
        "Alternate full-body strength sessions with short conditioning sessions (using the "
        "Conditioning category). Prescribe higher reps (10-20) with short rest (30-60 sec) on "
        "conditioning days."
    ),
    "general_fitness": (
        "Use full-body sessions at low weekly frequency, splitting into Upper Body/Lower Body as "
        "days/week increases, with at least one Conditioning day once there are 4+ days/week. Cover "
        "push, pull, legs, and core across the week."
    ),
    "endurance": (
        "Use ONLY Conditioning-category exercises on every training day - aerobic/circuit work, not "
        "push/pull/legs strength training. Prescribe higher reps or longer work intervals with short "
        "rest (30-60 sec)."
    ),
    "flexibility": (
        "Use ONLY Mobility-category exercises on every training day. Prescribe controlled reps "
        "(6-12) or holds (20-45 sec) with short rest (15-30 sec)."
    ),
}

RESPONSE_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "day_index": {"type": "INTEGER"},
            "label": {"type": "STRING"},
            "is_rest_day": {"type": "BOOLEAN"},
            "exercises": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "exercise_id": {"type": "INTEGER"},
                        "sets": {"type": "INTEGER"},
                        "reps": {"type": "INTEGER"},
                        "hold_seconds": {"type": "INTEGER"},
                        "rest_seconds": {"type": "INTEGER"},
                    },
                    "required": ["exercise_id", "sets", "rest_seconds"],
                },
            },
        },
        "required": ["day_index", "label", "is_rest_day", "exercises"],
    },
}

PROMPT_TEMPLATE = """You are a calisthenics and bodyweight-fitness programming assistant for a fitness app called Peakform.

Build a 7-day training cycle (day_index 0=Monday through day_index 6=Sunday) for a user with:
- Primary goal: {goal}
- Experience level: {experience}
- Training days per week: {days} (exactly {days} of the 7 days must have is_rest_day=false; the rest must be true)
- Minutes per session: {minutes}
- Available equipment: {equipment}

Programming guidance for this goal: {guidance}

Spread training days across the week rather than clustering them together, so the same muscles get \
at least a day of recovery before training again. Each training day should have {min_ex} to {max_ex} \
main exercises - estimate about {minutes_per_exercise} minutes per exercise for its sets, reps/hold, \
and rest combined, and leave roughly 10 minutes of the session for warm-up and cool-down (handled \
separately - do not include warm-up or cool-down exercises here). Avoid combining multiple exercises \
that train the same movement in nearly the same way in one session (e.g. do not put Push-up, Incline \
Push-up, and Knee Push-up in the same session). Order each day's exercises with skill or technically \
demanding work first, while the user is fresh.

You may ONLY reference exercises from this catalog, by their id. Never invent an id or use one not \
listed here:
{catalog}

For each exercise you choose, set sets (1-6) and EITHER reps (3-50) OR hold_seconds (5-180) matching \
that exercise's own movement_type exactly as given in the catalog (never set both), plus rest_seconds \
(15-240).

Return a JSON array of exactly 7 day objects, one per day_index 0 through 6, each with "exercises": [] \
for rest days."""


class WorkoutAIError(Exception):
    """Base class for all errors raised by this module."""


class WorkoutAIConfigurationError(WorkoutAIError):
    """Raised when the API key is missing, so the caller can fall back silently."""


class WorkoutAIRequestError(WorkoutAIError):
    """Raised on network failure or a non-success HTTP response."""


class WorkoutAIResponseError(WorkoutAIError):
    """Raised when Gemini's response cannot be validated into a usable plan."""


def _call_gemini(prompt, *, api_key, model):
    url = GEMINI_ENDPOINT_TEMPLATE.format(model=model, key=api_key)
    body = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": RESPONSE_SCHEMA,
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise WorkoutAIRequestError(f"Gemini API returned HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise WorkoutAIRequestError("Could not reach the Gemini API.") from exc
    except json.JSONDecodeError as exc:
        raise WorkoutAIResponseError("Gemini API response was not valid JSON.") from exc


def _extract_text(envelope):
    try:
        candidates = envelope["candidates"]
        if not candidates:
            raise WorkoutAIResponseError("Gemini returned no candidates.")
        return candidates[0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise WorkoutAIResponseError("Gemini response was missing expected fields.") from exc


def _eligible_candidates(all_exercises, experience_level, equipment):
    return [
        ex
        for ex in all_exercises
        if ex.category not in (MovementCategory.WARMUP, MovementCategory.COOLDOWN)
        and ex.suits_experience(experience_level)
        and ex.suits_equipment(equipment)
    ]


def _build_prompt(goal, experience_level, training_days_per_week, session_duration_minutes, equipment, candidates):
    goal_label = dict(PrimaryGoal.choices).get(goal, goal)
    experience_label = dict(ExperienceLevel.choices).get(experience_level, experience_level)
    equipment_labels = (
        ", ".join(dict(Equipment.choices).get(e, e) for e in equipment) if equipment else "none (bodyweight only)"
    )
    catalog = json.dumps(
        [
            {
                "id": ex.id,
                "name": ex.name,
                "category": ex.category,
                "movement_type": ex.movement_type,
                "difficulty": ex.difficulty_level,
            }
            for ex in candidates
        ]
    )
    return PROMPT_TEMPLATE.format(
        goal=goal_label,
        experience=experience_label,
        days=training_days_per_week,
        minutes=session_duration_minutes,
        equipment=equipment_labels,
        guidance=GOAL_GUIDANCE.get(goal, GOAL_GUIDANCE["general_fitness"]),
        min_ex=MIN_EXERCISES_PER_DAY,
        max_ex=MAX_EXERCISES_PER_DAY,
        minutes_per_exercise=MINUTES_PER_EXERCISE,
        catalog=catalog,
    )


def _clamp(value, low, high, default):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, value))


def _build_planned_exercise(raw_item, candidates_by_id):
    exercise_id = raw_item.get("exercise_id")
    exercise = candidates_by_id.get(exercise_id)
    if exercise is None:
        return None

    sets = _clamp(raw_item.get("sets"), MIN_SETS, MAX_SETS, exercise.default_sets)
    rest = _clamp(raw_item.get("rest_seconds"), MIN_REST_SECONDS, MAX_REST_SECONDS, exercise.default_rest_seconds)
    reps = hold = None
    if exercise.movement_type == MovementType.HOLD:
        hold = _clamp(
            raw_item.get("hold_seconds"), MIN_TARGET_HOLD_SECONDS, MAX_TARGET_HOLD_SECONDS, exercise.default_hold_seconds
        )
    else:
        reps = _clamp(raw_item.get("reps"), MIN_TARGET_REPS, MAX_TARGET_REPS, exercise.default_reps)

    return PlannedExercise(exercise=exercise, target_sets=sets, target_reps=reps, target_hold_seconds=hold, rest_seconds=rest)


def _validate_days(raw_days, candidates_by_id, training_days_per_week):
    if not isinstance(raw_days, list):
        raise WorkoutAIResponseError("Gemini's response was not a list of days.")

    by_index = {}
    for raw_day in raw_days:
        if not isinstance(raw_day, dict):
            continue
        try:
            day_index = int(raw_day["day_index"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= day_index <= 6 and day_index not in by_index:
            by_index[day_index] = raw_day

    if len(by_index) != 7:
        raise WorkoutAIResponseError("Gemini's plan did not cover all 7 days exactly once.")

    training_count = sum(1 for d in by_index.values() if not d.get("is_rest_day"))
    if training_count != training_days_per_week:
        raise WorkoutAIResponseError("Gemini's plan didn't match the requested training days per week.")

    planned_days = []
    for day_index in range(7):
        raw_day = by_index[day_index]
        if raw_day.get("is_rest_day"):
            planned_days.append(PlannedDay(day_index=day_index, label="Rest", is_rest_day=True))
            continue

        label = str(raw_day.get("label") or "Training")[:50]
        exercises = []
        for raw_item in raw_day.get("exercises") or []:
            if not isinstance(raw_item, dict):
                continue
            planned_exercise = _build_planned_exercise(raw_item, candidates_by_id)
            if planned_exercise is not None:
                exercises.append(planned_exercise)

        if len(exercises) < MIN_EXERCISES_PER_DAY:
            raise WorkoutAIResponseError(f"Day {day_index} did not have enough valid exercises.")

        planned_days.append(PlannedDay(day_index=day_index, label=label, is_rest_day=False, exercises=exercises))

    return planned_days


def generate_plan_with_ai(
    all_exercises, experience_level, equipment, goal, training_days_per_week, session_duration_minutes,
    *, api_key=None, model=None,
):
    """AI-assisted equivalent of generation.generate_plan_days.

    Raises WorkoutAIConfigurationError, WorkoutAIRequestError, or
    WorkoutAIResponseError on any failure - callers should catch
    WorkoutAIError and fall back to the deterministic generator.
    """
    api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
    if not api_key:
        raise WorkoutAIConfigurationError("The AI assistant is not configured on this server.")

    training_days = max(1, min(training_days_per_week, MAX_TRAINING_DAYS))
    candidates = _eligible_candidates(all_exercises, experience_level, equipment)
    if len(candidates) < MIN_EXERCISES_PER_DAY:
        raise WorkoutAIResponseError("Not enough matching exercises to build an AI plan.")
    candidates_by_id = {ex.id: ex for ex in candidates}

    model = model or getattr(settings, "GEMINI_MODEL", "gemini-3.1-flash-lite")
    prompt = _build_prompt(goal, experience_level, training_days, session_duration_minutes, equipment, candidates)

    envelope = _call_gemini(prompt, api_key=api_key, model=model)
    text = _extract_text(envelope)
    try:
        raw_days = json.loads(text)
    except json.JSONDecodeError as exc:
        raise WorkoutAIResponseError("Gemini's response was not valid JSON.") from exc

    planned_days = _validate_days(raw_days, candidates_by_id, training_days)

    warmup_pool, cooldown_pool = warmup_cooldown_pools(all_exercises, equipment)
    for day in planned_days:
        if day.is_rest_day:
            continue
        warmup_exercises = [_to_planned_exercise(ex) for ex in warmup_pool[:WARMUP_EXERCISE_COUNT]]
        cooldown_exercises = [_to_planned_exercise(ex) for ex in cooldown_pool[:COOLDOWN_EXERCISE_COUNT]]
        day.exercises = warmup_exercises + day.exercises + cooldown_exercises

    return planned_days
