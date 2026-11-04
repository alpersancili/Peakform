"""Seed the three hand-curated, named training programs (each offered at
Easy/Intermediate/Difficult tiers), transcribed from a fixed source
program. Exercise names map onto the existing Exercise catalog - run
seed_exercises first so every name here resolves.

Each exercise tuple is (exercise_name, prescription_display_text, sets,
reps_or_None, hold_seconds_or_None). `prescription` keeps the exact
source wording (including odd formats like a 20-minute skill-practice
block) even where the sets/reps/hold breakdown is a best-effort mapping
onto the numeric fields WorkoutPlanExercise needs when a user starts the
program for real.
"""

from django.core.management.base import BaseCommand, CommandError

from workouts.models import Exercise, ProgramTemplate, ProgramTemplateDay, ProgramTemplateExercise

PROGRAMS = [
    {
        "slug": "skill-focused",
        "name": "Skill-focused",
        "tagline": "Master advanced skills",
        "description": (
            "Heavy on static holds and skill progressions - planche, front lever, and "
            "handstand work - with just enough leg training to stay balanced. Best for "
            "athletes chasing a specific skill more than raw muscle size."
        ),
        "ratings": {"skill": 5, "muscle": 3, "strength": 4, "athleticism": 4},
        "order": 0,
        "difficulties": {
            "easy": [
                ("Push", 0, [
                    ("Planche Tuck", "6 x 8 sec", 6, None, 8),
                    ("Planche Lean", "4 x 15 sec", 4, None, 15),
                    ("Wall Handstand Hold", "4 x 30 sec", 4, None, 30),
                ]),
                ("Pull", 1, [
                    ("Front Lever Tuck", "6 x 8 sec", 6, None, 8),
                    ("Front Lever Raises", "3 x 5", 3, 5, None),
                    ("Skin the Cat", "3 x 5", 3, 5, None),
                ]),
                ("Rest", 2, None),
                ("Push", 3, [
                    ("Planche Tuck", "5 x 10 sec", 5, None, 10),
                    ("Wall Handstand Hold", "4 x 30 sec", 4, None, 30),
                    ("Pike Push-up", "3 x 8", 3, 8, None),
                ]),
                ("Pull", 4, [
                    ("Front Lever Tuck", "5 x 10 sec", 5, None, 10),
                    ("Scapular Pull-up", "3 x 10", 3, 10, None),
                    ("Hanging Leg Raises", "3 x 10", 3, 10, None),
                ]),
                ("Legs", 5, [
                    ("Pistol Squat", "3 x 6", 3, 6, None),
                    ("Jump Squat", "3 x 8", 3, 8, None),
                    ("L-sit", "3 x 10 sec", 3, None, 10),
                ]),
                ("Rest", 6, None),
            ],
            "intermediate": [
                ("Push", 0, [
                    ("Advanced Tuck Planche", "6 x 10 sec", 6, None, 10),
                    ("Planche Lean", "4 x 20 sec", 4, None, 20),
                    ("Handstand Push-up", "4 x 5", 4, 5, None),
                ]),
                ("Pull", 1, [
                    ("Advanced Tuck Front Lever", "6 x 10 sec", 6, None, 10),
                    ("Front Lever Raises", "4 x 5", 4, 5, None),
                    ("Pull-up", "3 x 8", 3, 8, None),
                ]),
                ("Rest", 2, None),
                ("Push", 3, [
                    ("Advanced Tuck Planche", "5 x 12 sec", 5, None, 12),
                    ("Freestanding Handstand Practice", "4 x 45 sec", 4, None, 45),
                    ("Wall Handstand Push-up", "4 x 6", 4, 6, None),
                ]),
                ("Pull", 4, [
                    ("Advanced Tuck Front Lever", "5 x 12 sec", 5, None, 12),
                    ("Front Lever Row", "4 x 6", 4, 6, None),
                    ("Muscle-up", "3 x 5", 3, 5, None),
                ]),
                ("Legs", 5, [
                    ("Pistol Squat", "4 x 6", 4, 6, None),
                    ("Jump Squat", "4 x 10", 4, 10, None),
                    ("L-sit", "4 x 20 sec", 4, None, 20),
                ]),
                ("Rest", 6, None),
            ],
            "difficult": [
                ("Push", 0, [
                    ("Straddle Planche", "6 x 8 sec", 6, None, 8),
                    ("Planche Push-up", "4 x 5", 4, 5, None),
                    ("Freestanding Handstand Push-up", "4 x 5", 4, 5, None),
                ]),
                ("Pull", 1, [
                    ("Straddle Front Lever", "6 x 10 sec", 6, None, 10),
                    ("Front Lever Raises", "4 x 6", 4, 6, None),
                    ("Front Lever Pull-up", "4 x 5", 4, 5, None),
                ]),
                ("Rest", 2, None),
                ("Push", 3, [
                    ("One Arm Handstand", "20 min practice", 1, None, 1200),
                    ("Planche", "5 x 8 sec", 5, None, 8),
                    ("Handstand Push-up", "4 x 6", 4, 6, None),
                ]),
                ("Pull", 4, [
                    ("Front Lever", "5 x 12 sec", 5, None, 12),
                    ("Front Lever Row", "4 x 8", 4, 8, None),
                    ("Muscle-up", "4 x 5", 4, 5, None),
                ]),
                ("Legs", 5, [
                    ("Pistol Squat", "4 x 8", 4, 8, None),
                    ("Jump Squat", "4 x 10 (explosive)", 4, 10, None),
                    ("Shrimp Squat", "3 x 8", 3, 8, None),
                ]),
                ("Rest", 6, None),
            ],
        },
    },
    {
        "slug": "strength-hypertrophy",
        "name": "Strength & Hypertrophy",
        "tagline": "Build muscle and strength",
        "description": (
            "Higher volume on push-ups, dips, pull-ups and squats - the classic "
            "bodyweight bodybuilding approach. Minimal static-hold skill work, maximum "
            "focus on reps and muscle growth."
        ),
        "ratings": {"skill": 2, "muscle": 5, "strength": 5, "athleticism": 3},
        "order": 1,
        "difficulties": {
            "easy": [
                ("Push", 0, [
                    ("Push-up", "3 x 10", 3, 10, None),
                    ("Dips", "3 x 6", 3, 6, None),
                    ("Pike Push-up", "3 x 8", 3, 8, None),
                    ("Diamond Push-up", "2 x 8", 2, 8, None),
                ]),
                ("Pull", 1, [
                    ("Pull-up", "3 x 5", 3, 5, None),
                    ("Chin-up", "3 x 6", 3, 6, None),
                    ("Table Row", "3 x 10", 3, 10, None),
                    ("Hanging Leg Raises", "3 x 10", 3, 10, None),
                ]),
                ("Rest", 2, None),
                ("Push", 3, [
                    ("Push-up", "3 x 12", 3, 12, None),
                    ("Dips", "3 x 8", 3, 8, None),
                    ("Pike Push-up", "3 x 8", 3, 8, None),
                    ("Bench Dip", "2 x 10", 2, 10, None),
                ]),
                ("Pull", 4, [
                    ("Pull-up", "3 x 6", 3, 6, None),
                    ("Chin-up", "3 x 8", 3, 8, None),
                    ("Table Row", "3 x 12", 3, 12, None),
                    ("Hanging Leg Raises", "3 x 10", 3, 10, None),
                ]),
                ("Legs", 5, [
                    ("Bodyweight Squat", "3 x 15", 3, 15, None),
                    ("Lunge", "3 x 10", 3, 10, None),
                    ("Calf Raise", "3 x 15", 3, 15, None),
                    ("Plank", "3 x 30 sec", 3, None, 30),
                ]),
                ("Rest", 6, None),
            ],
            "intermediate": [
                ("Push", 0, [
                    ("Dips", "4 x 10", 4, 10, None),
                    ("Push-up", "4 x 20", 4, 20, None),
                    ("Pike Push-up", "3 x 12", 3, 12, None),
                    ("Diamond Push-up", "3 x 12", 3, 12, None),
                ]),
                ("Pull", 1, [
                    ("Pull-up", "4 x 8", 4, 8, None),
                    ("Chin-up", "3 x 10", 3, 10, None),
                    ("Table Row", "4 x 12", 4, 12, None),
                    ("Hanging Leg Raises", "3 x 12", 3, 12, None),
                ]),
                ("Rest", 2, None),
                ("Push", 3, [
                    ("Decline Push-up", "4 x 15", 4, 15, None),
                    ("Dips", "4 x 10", 4, 10, None),
                    ("Handstand Push-up", "3 x 5", 3, 5, None),
                    ("Diamond Push-up", "3 x 15", 3, 15, None),
                ]),
                ("Pull", 4, [
                    ("Pull-up", "4 x 10", 4, 10, None),
                    ("Chin-up", "3 x 10", 3, 10, None),
                    ("Ring Rows", "3 x 12 (wide grip)", 3, 12, None),
                    ("Toes to Bar", "3 x 8", 3, 8, None),
                ]),
                ("Legs", 5, [
                    ("Pistol Squat", "3 x 6", 3, 6, None),
                    ("Bulgarian Split Squat", "4 x 10", 4, 10, None),
                    ("Jump Squat", "3 x 12", 3, 12, None),
                    ("Calf Raise", "4 x 15", 4, 15, None),
                ]),
                ("Rest", 6, None),
            ],
            "difficult": [
                ("Push", 0, [
                    ("Dips", "4 x 8 (weighted)", 4, 8, None),
                    ("Pseudo Planche Push-up", "4 x 10", 4, 10, None),
                    ("Handstand Push-up", "4 x 8", 4, 8, None),
                    ("Diamond Push-up", "3 x 20", 3, 20, None),
                ]),
                ("Pull", 1, [
                    ("Pull-up", "4 x 8 (weighted)", 4, 8, None),
                    ("Chin-up", "3 x 8 (weighted)", 3, 8, None),
                    ("Ring Rows", "4 x 12 (advanced)", 4, 12, None),
                    ("Toes to Bar", "4 x 12", 4, 12, None),
                ]),
                ("Rest", 2, None),
                ("Push", 3, [
                    ("Ring Dips", "4 x 10", 4, 10, None),
                    ("Archer Push-up", "4 x 10", 4, 10, None),
                    ("Freestanding Handstand Push-up", "4 x 6", 4, 6, None),
                    ("Decline Push-up", "3 x 20", 3, 20, None),
                ]),
                ("Pull", 4, [
                    ("Muscle-up", "4 x 5", 4, 5, None),
                    ("Pull-up", "4 x 8 (weighted)", 4, 8, None),
                    ("Front Lever Row", "4 x 8", 4, 8, None),
                    ("Hanging Leg Raises", "4 x 15", 4, 15, None),
                ]),
                ("Legs", 5, [
                    ("Pistol Squat", "4 x 8", 4, 8, None),
                    ("Bulgarian Split Squat", "4 x 12", 4, 12, None),
                    ("Shrimp Squat", "3 x 10", 3, 10, None),
                    ("Jump Squat", "4 x 15", 4, 15, None),
                ]),
                ("Rest", 6, None),
            ],
        },
    },
    {
        "slug": "mixed-training",
        "name": "Mixed Training",
        "tagline": "All-round calisthenics athlete",
        "description": (
            "The most balanced option: practise skills while also developing strength, "
            "muscle and explosive power. A good starting point if you can already perform "
            "clean pull-ups, dips and handstand push-ups."
        ),
        "ratings": {"skill": 5, "muscle": 4, "strength": 4, "athleticism": 5},
        "order": 2,
        "difficulties": {
            "easy": [
                ("Push", 0, [
                    ("Planche Tuck", "4 x 8 sec", 4, None, 8),
                    ("Push-up", "3 x 12", 3, 12, None),
                    ("Dips", "3 x 6", 3, 6, None),
                    ("Pike Push-up", "3 x 8", 3, 8, None),
                ]),
                ("Pull", 1, [
                    ("Front Lever Tuck", "4 x 8 sec", 4, None, 8),
                    ("Pull-up", "3 x 5", 3, 5, None),
                    ("Table Row", "3 x 10", 3, 10, None),
                    ("Hanging Leg Raises", "3 x 10", 3, 10, None),
                ]),
                ("Rest", 2, None),
                ("Push", 3, [
                    ("Freestanding Handstand Practice", "10 min practice", 1, None, 600),
                    ("Planche Lean", "3 x 15 sec", 3, None, 15),
                    ("Dips", "3 x 8", 3, 8, None),
                    ("Push-up", "3 x 12", 3, 12, None),
                ]),
                ("Pull", 4, [
                    ("Front Lever Tuck", "4 x 8 sec (progression)", 4, None, 8),
                    ("Chin-up", "3 x 6", 3, 6, None),
                    ("Table Row", "3 x 12", 3, 12, None),
                    ("Hanging Leg Raises", "3 x 10", 3, 10, None),
                ]),
                ("Legs", 5, [
                    ("Pistol Squat", "3 x 6", 3, 6, None),
                    ("Jump Squat", "3 x 8", 3, 8, None),
                    ("Lunge", "3 x 10", 3, 10, None),
                    ("L-sit", "3 x 10 sec", 3, None, 10),
                ]),
                ("Rest", 6, None),
            ],
            "intermediate": [
                ("Push", 0, [
                    ("Advanced Tuck Planche", "5 x 10 sec", 5, None, 10),
                    ("Planche Push-up", "3 x 6", 3, 6, None),
                    ("Handstand Push-up", "4 x 5", 4, 5, None),
                    ("Dips", "3 x 10", 3, 10, None),
                ]),
                ("Pull", 1, [
                    ("Advanced Tuck Front Lever", "5 x 10 sec", 5, None, 10),
                    ("Front Lever Row", "3 x 6", 3, 6, None),
                    ("Pull-up", "4 x 8", 4, 8, None),
                    ("Hanging Leg Raises", "3 x 12", 3, 12, None),
                ]),
                ("Rest", 2, None),
                ("Push", 3, [
                    ("One Arm Handstand", "15 min practice", 1, None, 900),
                    ("Freestanding Handstand Practice", "3 x 40 sec", 3, None, 40),
                    ("Handstand Push-up", "4 x 6", 4, 6, None),
                    ("Diamond Push-up", "3 x 12", 3, 12, None),
                ]),
                ("Pull", 4, [
                    ("Muscle-up", "4 x 3", 4, 3, None),
                    ("Pull-up", "3 x 8", 3, 8, None),
                    ("Front Lever Raises", "3 x 5", 3, 5, None),
                    ("Chin-up", "3 x 10", 3, 10, None),
                ]),
                ("Legs", 5, [
                    ("Pistol Squat", "4 x 6", 4, 6, None),
                    ("Bulgarian Split Squat", "3 x 10", 3, 10, None),
                    ("Jump Squat", "4 x 10", 4, 10, None),
                    ("L-sit", "3 x 20 sec", 3, None, 20),
                ]),
                ("Rest", 6, None),
            ],
            "difficult": [
                ("Push", 0, [
                    ("Straddle Planche", "5 x 8 sec", 5, None, 8),
                    ("Planche Push-up", "4 x 5", 4, 5, None),
                    ("Freestanding Handstand Push-up", "4 x 6", 4, 6, None),
                    ("Dips", "3 x 8 (weighted)", 3, 8, None),
                ]),
                ("Pull", 1, [
                    ("Straddle Front Lever", "5 x 10 sec", 5, None, 10),
                    ("Front Lever Pull-up", "4 x 5", 4, 5, None),
                    ("Pull-up", "4 x 8 (weighted)", 4, 8, None),
                    ("Toes to Bar", "3 x 12", 3, 12, None),
                ]),
                ("Rest", 2, None),
                ("Push", 3, [
                    ("One Arm Handstand", "20 min practice", 1, None, 1200),
                    ("Planche", "4 x 8 sec", 4, None, 8),
                    ("Handstand Push-up", "4 x 8", 4, 8, None),
                    ("Ring Dips", "3 x 10", 3, 10, None),
                ]),
                ("Pull", 4, [
                    ("Muscle-up", "5 x 4", 5, 4, None),
                    ("Front Lever Row", "4 x 8", 4, 8, None),
                    ("Chin-up", "3 x 8 (weighted)", 3, 8, None),
                    ("Hanging Leg Raises", "4 x 15", 4, 15, None),
                ]),
                ("Legs", 5, [
                    ("Pistol Squat", "4 x 8", 4, 8, None),
                    ("Shrimp Squat", "3 x 10", 3, 10, None),
                    ("Bulgarian Split Squat", "3 x 12", 3, 12, None),
                    ("Jump Squat", "4 x 10 (explosive)", 4, 10, None),
                ]),
                ("Rest", 6, None),
            ],
        },
    },
]


class Command(BaseCommand):
    help = "Seed the curated named training programs (Skill-focused, Strength & Hypertrophy, Mixed Training)."

    def handle(self, *args, **options):
        exercise_cache = {}
        programs_created = 0
        days_created = 0
        exercises_created = 0

        def get_exercise(name):
            if name not in exercise_cache:
                try:
                    exercise_cache[name] = Exercise.objects.get(name=name)
                except Exercise.DoesNotExist as exc:
                    raise CommandError(
                        f"Exercise '{name}' not found - run `seed_exercises` first."
                    ) from exc
            return exercise_cache[name]

        for program_data in PROGRAMS:
            ratings = program_data["ratings"]
            template, was_created = ProgramTemplate.objects.update_or_create(
                slug=program_data["slug"],
                defaults=dict(
                    name=program_data["name"],
                    tagline=program_data["tagline"],
                    description=program_data["description"],
                    skill_rating=ratings["skill"],
                    muscle_rating=ratings["muscle"],
                    strength_rating=ratings["strength"],
                    athleticism_rating=ratings["athleticism"],
                    order=program_data["order"],
                ),
            )
            programs_created += int(was_created)

            for difficulty, days in program_data["difficulties"].items():
                for label, day_index, exercises in days:
                    day, day_was_created = ProgramTemplateDay.objects.update_or_create(
                        template=template,
                        difficulty=difficulty,
                        day_index=day_index,
                        defaults=dict(label=label, is_rest_day=exercises is None),
                    )
                    days_created += int(day_was_created)

                    day.exercises.all().delete()
                    if exercises is None:
                        continue
                    for order, (ex_name, prescription, sets, reps, hold) in enumerate(exercises):
                        ProgramTemplateExercise.objects.create(
                            day=day,
                            exercise=get_exercise(ex_name),
                            order=order,
                            prescription=prescription,
                            target_sets=sets,
                            target_reps=reps,
                            target_hold_seconds=hold,
                        )
                        exercises_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {programs_created} new program(s), {days_created} new day(s), "
            f"{exercises_created} exercise prescriptions written."
        ))
