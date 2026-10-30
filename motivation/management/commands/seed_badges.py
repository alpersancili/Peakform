from django.core.management.base import BaseCommand

from motivation.models import Badge, BadgeCriteria

BADGES = [
    dict(slug="first-workout", name="First Steps", description="Complete your first workout.",
         criteria_type=BadgeCriteria.TOTAL_WORKOUTS, threshold=1),
    dict(slug="ten-workouts", name="Consistent", description="Complete 10 workouts.",
         criteria_type=BadgeCriteria.TOTAL_WORKOUTS, threshold=10),
    dict(slug="twenty-five-workouts", name="Dedicated", description="Complete 25 workouts.",
         criteria_type=BadgeCriteria.TOTAL_WORKOUTS, threshold=25),
    dict(slug="fifty-workouts", name="Peak Performer", description="Complete 50 workouts.",
         criteria_type=BadgeCriteria.TOTAL_WORKOUTS, threshold=50),
    dict(slug="three-day-streak", name="Building Momentum", description="Reach a 3-day streak.",
         criteria_type=BadgeCriteria.STREAK_DAYS, threshold=3),
    dict(slug="seven-day-streak", name="Week Strong", description="Reach a 7-day streak.",
         criteria_type=BadgeCriteria.STREAK_DAYS, threshold=7),
    dict(slug="fourteen-day-streak", name="Two Weeks Strong", description="Reach a 14-day streak.",
         criteria_type=BadgeCriteria.STREAK_DAYS, threshold=14),
    dict(slug="thirty-day-streak", name="Monthly Momentum", description="Reach a 30-day streak.",
         criteria_type=BadgeCriteria.STREAK_DAYS, threshold=30),
    dict(slug="ten-meals-logged", name="Food Logger", description="Log 10 meals.",
         criteria_type=BadgeCriteria.TOTAL_MEALS_LOGGED, threshold=10),
    dict(slug="fifty-meals-logged", name="Nutrition Pro", description="Log 50 meals.",
         criteria_type=BadgeCriteria.TOTAL_MEALS_LOGGED, threshold=50),
]


class Command(BaseCommand):
    help = "Seed the badge/milestone definitions."

    def handle(self, *args, **options):
        created = 0
        for data in BADGES:
            _, was_created = Badge.objects.update_or_create(slug=data["slug"], defaults=data)
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Seeded {created} new badges ({len(BADGES)} total)."))
