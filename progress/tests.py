import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from nutrition.models import WaterLog
from workouts.models import SessionStatus, WorkoutSession

from .models import ProgressEntry


class ProgressEntryModelTests(TestCase):
    def test_str(self):
        user = User.objects.create_user("athlete", "athlete@example.com", "password123!")
        entry = ProgressEntry.objects.create(user=user, date=timezone.localdate(), weight_kg=70)
        self.assertIn("70", str(entry))

    def test_one_entry_per_user_per_day(self):
        user = User.objects.create_user("athlete", "athlete@example.com", "password123!")
        today = timezone.localdate()
        ProgressEntry.objects.create(user=user, date=today, weight_kg=70)
        with self.assertRaises(Exception):
            ProgressEntry.objects.create(user=user, date=today, weight_kg=71)


class ProgressOverviewViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "athlete@example.com", "password123!")
        self.client.login(username="athlete", password="password123!")

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("progress:overview"))
        self.assertEqual(response.status_code, 302)

    def test_loads_with_no_entries(self):
        response = self.client.get(reverse("progress:overview"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Log your weight below to start a trend.")

    def test_can_log_a_new_entry(self):
        response = self.client.post(
            reverse("progress:overview"),
            {"date": "2026-10-01", "weight_kg": "72.5", "waist_cm": "80", "notes": "Felt good"},
        )
        self.assertRedirects(response, reverse("progress:overview"))
        entry = ProgressEntry.objects.get(user=self.user)
        self.assertEqual(entry.weight_kg, 72.5)
        self.assertEqual(entry.waist_cm, 80)
        self.assertEqual(entry.notes, "Felt good")

    def test_logging_same_date_again_updates_instead_of_duplicating(self):
        self.client.post(reverse("progress:overview"), {"date": "2026-10-01", "weight_kg": "72.5"})
        self.client.post(reverse("progress:overview"), {"date": "2026-10-01", "weight_kg": "73.0"})
        self.assertEqual(ProgressEntry.objects.filter(user=self.user).count(), 1)
        self.assertEqual(ProgressEntry.objects.get(user=self.user).weight_kg, 73.0)

    def test_weight_change_shown_across_entries(self):
        ProgressEntry.objects.create(user=self.user, date=datetime.date(2026, 9, 1), weight_kg=75)
        ProgressEntry.objects.create(user=self.user, date=datetime.date(2026, 10, 1), weight_kg=73)
        response = self.client.get(reverse("progress:overview"))
        self.assertEqual(response.context["weight_change"], -2.0)

    def test_total_completed_workouts_counted(self):
        WorkoutSession.objects.create(user=self.user, status=SessionStatus.COMPLETED)
        WorkoutSession.objects.create(user=self.user, status=SessionStatus.IN_PROGRESS)
        response = self.client.get(reverse("progress:overview"))
        self.assertEqual(response.context["total_completed_workouts"], 1)

    def test_calorie_consistency_counts_only_this_users_logged_days(self):
        from nutrition.models import Food, MealEntry

        food = Food.objects.create(name="Oats", calories=500, protein_g=20, carbs_g=60, fat_g=10)
        MealEntry.objects.create(user=self.user, food=food, meal_category="breakfast", quantity=1, logged_at=timezone.now())
        response = self.client.get(reverse("progress:overview"))
        self.assertEqual(response.context["calorie_consistency"]["logged_days"], 1)

    def test_water_history_reflects_logged_amounts(self):
        today = timezone.localdate()
        WaterLog.objects.create(user=self.user, amount_ml=500, logged_at=timezone.now())
        response = self.client.get(reverse("progress:overview"))
        todays_point = next(d for d in response.context["water_history"] if d["date"] == today)
        self.assertEqual(todays_point["amount"], 500)


class ProgressEntryDeleteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "athlete@example.com", "password123!")
        self.other = User.objects.create_user("other", "other@example.com", "password123!")
        self.entry = ProgressEntry.objects.create(user=self.user, date=timezone.localdate(), weight_kg=70)

    def test_owner_can_delete(self):
        self.client.login(username="athlete", password="password123!")
        self.client.post(reverse("progress:entry_delete", args=[self.entry.id]))
        self.assertFalse(ProgressEntry.objects.filter(id=self.entry.id).exists())

    def test_cannot_delete_another_users_entry(self):
        self.client.login(username="other", password="password123!")
        response = self.client.post(reverse("progress:entry_delete", args=[self.entry.id]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(ProgressEntry.objects.filter(id=self.entry.id).exists())
