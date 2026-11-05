"""Mobility & recovery routines.

Groups the exercise library's mobility-category exercises into named
routines by target area, so a user can go straight to "loosen up my
hips" rather than browsing the whole library. Membership is keyword
matching against each exercise's own target_muscles text rather than a
separately maintained list, so a newly seeded mobility exercise picks
up automatically if its muscles mention one of these areas.
"""

from .models import Exercise, MovementCategory

ROUTINE_AREAS = [
    ("wrists", "Wrists & forearms", ["wrist", "forearm"]),
    ("shoulders", "Shoulders", ["shoulder"]),
    ("thoracic", "Thoracic spine", ["thoracic"]),
    ("hips", "Hips", ["hip"]),
    ("hamstrings", "Hamstrings", ["hamstring"]),
    ("ankles", "Ankles & calves", ["ankle", "calf", "calves"]),
]

# Which routine best follows a session with this focus category, e.g. a
# pull day (back, biceps, grip) points toward shoulder/wrist mobility.
FOCUS_TO_ROUTINE_KEY = {
    "push": "shoulders",
    "pull": "shoulders",
    "legs": "hips",
    "core": "thoracic",
    "skill": "wrists",
    "full body": "hips",
}


def mobility_routines():
    """Every named routine that has at least one matching exercise."""
    exercises = list(Exercise.objects.filter(category=MovementCategory.MOBILITY))
    routines = []
    for key, label, keywords in ROUTINE_AREAS:
        matches = [ex for ex in exercises if any(kw in ex.target_muscles.lower() for kw in keywords)]
        if matches:
            routines.append({"key": key, "label": label, "exercises": matches})
    return routines


def routine_for_focus_areas(focus_areas):
    """The single most relevant routine for a workout's focus areas, or None.

    Best-effort: returns None rather than guessing when nothing obviously
    fits, instead of forcing an irrelevant routine on every workout.
    """
    routines_by_key = {routine["key"]: routine for routine in mobility_routines()}
    for focus in focus_areas:
        key = FOCUS_TO_ROUTINE_KEY.get(focus.lower())
        if key and key in routines_by_key:
            return routines_by_key[key]
    return None
