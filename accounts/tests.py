from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import UserProfile


class RegistrationTests(TestCase):
    def test_register_creates_user_and_profile_then_redirects_to_onboarding(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "newathlete",
                "email": "new@example.com",
                "password1": "a-strong-pass-123",
                "password2": "a-strong-pass-123",
            },
        )
        self.assertRedirects(response, reverse("accounts:onboarding"))
        user = User.objects.get(username="newathlete")
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user("existing", "dupe@example.com", "password123!")
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "another",
                "email": "dupe@example.com",
                "password1": "a-strong-pass-123",
                "password2": "a-strong-pass-123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="another").exists())


class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "athlete@example.com", "password123!")

    def test_login_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "athlete", "password": "password123!"},
        )
        self.assertRedirects(response, reverse("nutrition:dashboard"))

    def test_logout_requires_post(self):
        self.client.login(username="athlete", password="password123!")
        response = self.client.get(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 405)


class OnboardingAccessTests(TestCase):
    def test_onboarding_requires_login(self):
        response = self.client.get(reverse("accounts:onboarding"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_profile_requires_login(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 302)


class OnboardingFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "athlete@example.com", "password123!")
        self.client.login(username="athlete", password="password123!")

    def test_onboarding_with_imperial_units_converts_to_metric(self):
        response = self.client.post(
            reverse("accounts:onboarding"),
            {
                "date_of_birth": "1995-06-15",
                "sex": "male",
                "country": "United States",
                "preferred_units": "imperial",
                "height_ft": "5",
                "height_in": "10",
                "weight_lb": "180",
                "activity_level": "moderate",
                "experience_level": "intermediate",
                "primary_goal": "strength",
                "training_days_per_week": "4",
                "session_duration_minutes": "60",
                "equipment": ["pull_up_bar", "rings"],
                "dietary_preferences": ["none"],
            },
        )
        self.assertRedirects(response, reverse("nutrition:dashboard"))

        profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(profile.onboarding_completed)
        self.assertAlmostEqual(profile.height_cm, 177.8, places=1)
        self.assertAlmostEqual(profile.weight_kg, 81.65, places=1)
        self.assertEqual(sorted(profile.equipment), ["pull_up_bar", "rings"])

    def test_onboarding_with_metric_units(self):
        response = self.client.post(
            reverse("accounts:onboarding"),
            {
                "date_of_birth": "1998-01-01",
                "sex": "female",
                "country": "Germany",
                "preferred_units": "metric",
                "height_cm_input": "168",
                "weight_kg_input": "62",
                "activity_level": "light",
                "experience_level": "beginner",
                "primary_goal": "general_fitness",
                "training_days_per_week": "3",
                "session_duration_minutes": "30",
                "equipment": ["none"],
                "dietary_preferences": ["vegetarian"],
            },
        )
        self.assertRedirects(response, reverse("nutrition:dashboard"))
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.height_cm, 168.0)
        self.assertEqual(profile.weight_kg, 62.0)

    def test_onboarding_missing_height_shows_error(self):
        response = self.client.post(
            reverse("accounts:onboarding"),
            {
                "preferred_units": "metric",
                "activity_level": "moderate",
                "experience_level": "beginner",
                "primary_goal": "general_fitness",
                "training_days_per_week": "3",
                "session_duration_minutes": "45",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(UserProfile.objects.get(user=self.user).onboarding_completed)

    def test_completed_onboarding_redirects_away(self):
        profile = UserProfile.objects.get(user=self.user)
        profile.onboarding_completed = True
        profile.save()
        response = self.client.get(reverse("accounts:onboarding"))
        self.assertRedirects(response, reverse("nutrition:dashboard"))


class ProfileEditTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "athlete@example.com", "password123!")
        self.client.login(username="athlete", password="password123!")
        self.profile = UserProfile.objects.get(user=self.user)
        self.profile.height_cm = 170
        self.profile.weight_kg = 70
        self.profile.onboarding_completed = True
        self.profile.save()

    def test_profile_edit_updates_existing_profile(self):
        response = self.client.post(
            reverse("accounts:profile_edit"),
            {
                "sex": "male",
                "preferred_units": "metric",
                "height_cm_input": "172",
                "weight_kg_input": "71",
                "activity_level": "active",
                "experience_level": "advanced",
                "primary_goal": "muscle_gain",
                "training_days_per_week": "5",
                "session_duration_minutes": "50",
                "equipment": ["full_gym"],
                "dietary_preferences": [],
            },
        )
        self.assertRedirects(response, reverse("accounts:profile"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.height_cm, 172.0)
        self.assertEqual(self.profile.primary_goal, "muscle_gain")
