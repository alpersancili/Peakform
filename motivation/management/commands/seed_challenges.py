from django.core.management.base import BaseCommand

from motivation.models import Challenge, ChallengeCriteria

CHALLENGES = [
    dict(slug="weekly-three-workouts", name="Triple Threat", description="Complete 3 workouts this week.",
         criteria_type=ChallengeCriteria.WEEKLY_WORKOUTS, target=3, xp_reward=30),
    dict(slug="weekly-five-workouts", name="Five a Week", description="Complete 5 workouts this week.",
         criteria_type=ChallengeCriteria.WEEKLY_WORKOUTS, target=5, xp_reward=50),
    dict(slug="weekly-five-log-days", name="Food Diary", description="Log food on 5 days this week.",
         criteria_type=ChallengeCriteria.WEEKLY_MEAL_LOG_DAYS, target=5, xp_reward=30),
    dict(slug="weekly-hydration", name="Hydration Streak", description="Hit your water goal on 4 days this week.",
         criteria_type=ChallengeCriteria.WEEKLY_WATER_GOAL_DAYS, target=4, xp_reward=25),
]


class Command(BaseCommand):
    help = "Seed the weekly challenge definitions."

    def handle(self, *args, **options):
        created = 0
        for data in CHALLENGES:
            _, was_created = Challenge.objects.update_or_create(slug=data["slug"], defaults=data)
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Seeded {created} new challenges ({len(CHALLENGES)} total)."))
