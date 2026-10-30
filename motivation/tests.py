from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import ExperienceLevel, PrimaryGoal
from nutrition.models import Food, MealEntry
from workouts.models import SessionStatus, WorkoutPlan, WorkoutPlanDay, WorkoutSession

from .badges import evaluate_badges
from .models import Badge, BadgeCriteria, UserBadge
from .streaks import calculate_current_streak, weekly_workout_progress


def make_plan_with_rest_days(user, rest_weekdays, training_days_per_week=3):
    plan = WorkoutPlan.objects.create(
        user=user, goal=PrimaryGoal.GENERAL_FITNESS, experience_level=ExperienceLevel.BEGINNER,
        training_days_per_week=training_days_per_week, session_duration_minutes=45, is_active=True,
    )
    for day_index in range(7):
        WorkoutPlanDay.objects.create(plan=plan, day_index=day_index, label="Rest" if day_index in rest_weekdays else "Training",
                                       is_rest_day=day_index in rest_weekdays)
    return plan


class StreakTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "a@example.com", "password123!")
        self.food = Food.objects.create(name="Oats", calories=150, protein_g=5, carbs_g=27, fat_g=2)

    def _log_meal(self, date):
        entry = MealEntry(user=self.user, food=self.food, meal_category="breakfast", quantity=1)
        entry.logged_at = timezone.make_aware(timezone.datetime(date.year, date.month, date.day, 8, 0))
        entry.save()

    def test_no_activity_and_no_plan_gives_zero_streak(self):
        self.assertEqual(calculate_current_streak(self.user), 0)

    def test_consecutive_days_of_activity_count(self):
        today = timezone.localdate()
        for offset in range(3):
            self._log_meal(today - timedelta(days=offset))
        self.assertEqual(calculate_current_streak(self.user, today=today), 3)

    def test_gap_in_activity_breaks_streak(self):
        today = timezone.localdate()
        self._log_meal(today)
        self._log_meal(today - timedelta(days=1))
        # Gap at today-2 (no plan, so every day requires activity)
        self._log_meal(today - timedelta(days=3))
        self.assertEqual(calculate_current_streak(self.user, today=today), 2)

    def test_today_with_no_activity_yet_does_not_break_streak(self):
        today = timezone.localdate()
        self._log_meal(today - timedelta(days=1))
        self._log_meal(today - timedelta(days=2))
        self.assertEqual(calculate_current_streak(self.user, today=today), 2)

    def test_scheduled_rest_day_does_not_break_streak(self):
        today = timezone.localdate()
        # Rest day scheduled for today's weekday.
        make_plan_with_rest_days(self.user, rest_weekdays={today.weekday()})
        self._log_meal(today - timedelta(days=1))
        self._log_meal(today - timedelta(days=2))
        # today is a rest day (no activity needed), and the two days before have activity.
        self.assertEqual(calculate_current_streak(self.user, today=today), 2)

    def test_completed_workout_counts_as_activity(self):
        today = timezone.localdate()
        WorkoutSession.objects.create(user=self.user, date=today, status=SessionStatus.COMPLETED)
        self.assertEqual(calculate_current_streak(self.user, today=today), 1)

    def test_in_progress_workout_does_not_count(self):
        today = timezone.localdate()
        WorkoutSession.objects.create(user=self.user, date=today, status=SessionStatus.IN_PROGRESS)
        self.assertEqual(calculate_current_streak(self.user, today=today), 0)


class WeeklyProgressTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "a@example.com", "password123!")

    def test_no_plan_gives_zero_target(self):
        progress = weekly_workout_progress(self.user)
        self.assertEqual(progress["target"], 0)

    def test_counts_completed_sessions_within_the_week(self):
        make_plan_with_rest_days(self.user, rest_weekdays=set(), training_days_per_week=4)
        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        WorkoutSession.objects.create(user=self.user, date=week_start, status=SessionStatus.COMPLETED)
        WorkoutSession.objects.create(user=self.user, date=today, status=SessionStatus.COMPLETED)
        # Outside this week (last week) should not count.
        WorkoutSession.objects.create(user=self.user, date=week_start - timedelta(days=1), status=SessionStatus.COMPLETED)

        progress = weekly_workout_progress(self.user, today=today)
        self.assertEqual(progress["completed"], 2)
        self.assertEqual(progress["target"], 4)


class BadgeEvaluationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "a@example.com", "password123!")
        Badge.objects.create(slug="first-workout", name="First Steps", description="d",
                              criteria_type=BadgeCriteria.TOTAL_WORKOUTS, threshold=1)
        Badge.objects.create(slug="ten-workouts", name="Consistent", description="d",
                              criteria_type=BadgeCriteria.TOTAL_WORKOUTS, threshold=10)
        Badge.objects.create(slug="three-streak", name="Momentum", description="d",
                              criteria_type=BadgeCriteria.STREAK_DAYS, threshold=3)

    def test_awards_badge_when_threshold_met(self):
        WorkoutSession.objects.create(user=self.user, status=SessionStatus.COMPLETED)
        newly_earned = evaluate_badges(self.user)
        self.assertEqual([b.slug for b in newly_earned], ["first-workout"])
        self.assertTrue(UserBadge.objects.filter(user=self.user, badge__slug="first-workout").exists())

    def test_does_not_re_award_already_earned_badge(self):
        WorkoutSession.objects.create(user=self.user, status=SessionStatus.COMPLETED)
        evaluate_badges(self.user)
        newly_earned_again = evaluate_badges(self.user)
        self.assertEqual(newly_earned_again, [])
        self.assertEqual(UserBadge.objects.filter(user=self.user).count(), 1)

    def test_badge_not_awarded_below_threshold(self):
        WorkoutSession.objects.create(user=self.user, status=SessionStatus.COMPLETED)
        newly_earned = evaluate_badges(self.user)
        self.assertNotIn("ten-workouts", [b.slug for b in newly_earned])

    def test_badge_persists_even_if_streak_later_drops(self):
        # Simulate having earned a streak badge; it must not be revoked just
        # because evaluate_badges is re-run and the stat value has since
        # changed (badges are only ever added, never removed by this path).
        badge = Badge.objects.get(slug="three-streak")
        UserBadge.objects.create(user=self.user, badge=badge)
        evaluate_badges(self.user)
        self.assertTrue(UserBadge.objects.filter(user=self.user, badge=badge).exists())


class BadgesListViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "a@example.com", "password123!")
        self.client.login(username="athlete", password="password123!")
        Badge.objects.create(slug="first-workout", name="First Steps", description="d",
                              criteria_type=BadgeCriteria.TOTAL_WORKOUTS, threshold=1)

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("motivation:badges_list"))
        self.assertEqual(response.status_code, 302)

    def test_shows_locked_and_earned_badges(self):
        response = self.client.get(reverse("motivation:badges_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Locked")

        WorkoutSession.objects.create(user=self.user, status=SessionStatus.COMPLETED)
        evaluate_badges(self.user)
        response = self.client.get(reverse("motivation:badges_list"))
        self.assertContains(response, "Earned")
