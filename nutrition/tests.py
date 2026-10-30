from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import ActivityLevel, PrimaryGoal, Sex, UserProfile

from . import views as views_module
from .ai_client import (
    GeminiConfigurationError,
    GeminiRequestError,
    GeminiResponseError,
    parse_food_description,
)
from .ai_rate_limit import RateLimitExceeded, record_attempt_or_raise, requests_remaining_today
from .calculations import (
    calculate_bmi,
    calculate_bmr,
    calculate_daily_targets,
    calculate_tdee,
)
from .models import AIFoodLogRequest, Food, MealEntry, StepLog, WaterLog


class CalculationTests(TestCase):
    def test_bmi(self):
        self.assertEqual(calculate_bmi(70, 175), 22.9)

    def test_bmi_missing_data_returns_none(self):
        self.assertIsNone(calculate_bmi(None, 175))
        self.assertIsNone(calculate_bmi(70, None))

    def test_bmr_male(self):
        # 10*80 + 6.25*180 - 5*30 + 5 = 800 + 1125 - 150 + 5 = 1780
        self.assertEqual(calculate_bmr(80, 180, 30, Sex.MALE), 1780)

    def test_bmr_female(self):
        # 10*60 + 6.25*165 - 5*25 - 161 = 600 + 1031.25 - 125 - 161 = 1345.25
        self.assertAlmostEqual(calculate_bmr(60, 165, 25, Sex.FEMALE), 1345, delta=1)

    def test_bmr_unspecified_is_midpoint(self):
        male = calculate_bmr(75, 175, 28, Sex.MALE)
        female = calculate_bmr(75, 175, 28, Sex.FEMALE)
        unspecified = calculate_bmr(75, 175, 28, Sex.UNSPECIFIED)
        self.assertAlmostEqual(unspecified, (male + female) / 2, delta=1)

    def test_tdee_scales_by_activity(self):
        bmr = 1700
        sedentary = calculate_tdee(bmr, ActivityLevel.SEDENTARY)
        active = calculate_tdee(bmr, ActivityLevel.VERY_ACTIVE)
        self.assertLess(sedentary, active)
        self.assertEqual(sedentary, round(1700 * 1.2))

    def test_daily_targets_fat_loss_is_below_maintenance(self):
        targets = calculate_daily_targets(
            weight_kg=80, height_cm=180, age=30, sex=Sex.MALE,
            activity_level=ActivityLevel.MODERATE, primary_goal=PrimaryGoal.FAT_LOSS,
        )
        maintenance = calculate_daily_targets(
            weight_kg=80, height_cm=180, age=30, sex=Sex.MALE,
            activity_level=ActivityLevel.MODERATE, primary_goal=PrimaryGoal.GENERAL_FITNESS,
        )
        self.assertLess(targets.calories, maintenance.calories)

    def test_daily_targets_respects_safety_floor(self):
        # Very light, small, older user with a large deficit goal shouldn't
        # be pushed below the minimum safe calorie floor.
        targets = calculate_daily_targets(
            weight_kg=45, height_cm=150, age=70, sex=Sex.FEMALE,
            activity_level=ActivityLevel.SEDENTARY, primary_goal=PrimaryGoal.FAT_LOSS,
        )
        self.assertGreaterEqual(targets.calories, 1200)

    def test_daily_targets_none_without_body_data(self):
        self.assertIsNone(
            calculate_daily_targets(
                weight_kg=None, height_cm=None, age=None, sex=Sex.MALE,
                activity_level=ActivityLevel.MODERATE, primary_goal=PrimaryGoal.GENERAL_FITNESS,
            )
        )

    def test_daily_targets_override_calories_used_directly(self):
        targets = calculate_daily_targets(
            weight_kg=80, height_cm=180, age=30, sex=Sex.MALE,
            activity_level=ActivityLevel.MODERATE, primary_goal=PrimaryGoal.GENERAL_FITNESS,
            override_calories=2500,
        )
        self.assertEqual(targets.calories, 2500)

    def test_macro_grams_account_for_full_calorie_target(self):
        targets = calculate_daily_targets(
            weight_kg=80, height_cm=180, age=30, sex=Sex.MALE,
            activity_level=ActivityLevel.MODERATE, primary_goal=PrimaryGoal.GENERAL_FITNESS,
        )
        reconstructed = targets.protein_g * 4 + targets.carbs_g * 4 + targets.fat_g * 9
        self.assertAlmostEqual(reconstructed, targets.calories, delta=20)


class DashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "athlete@example.com", "password123!")
        self.profile = UserProfile.objects.get(user=self.user)
        self.profile.height_cm = 180
        self.profile.weight_kg = 80
        self.profile.date_of_birth = "1995-01-01"
        self.profile.sex = Sex.MALE
        self.profile.save()
        self.client.login(username="athlete", password="password123!")
        self.food = Food.objects.create(
            name="Test Chicken", serving_size=100, serving_unit="g",
            calories=165, protein_g=31, carbs_g=0, fat_g=3.6,
        )

    def test_dashboard_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("nutrition:dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_loads_with_targets(self):
        response = self.client.get(reverse("nutrition:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Calories")

    def test_dashboard_without_body_data_shows_prompt(self):
        self.profile.height_cm = None
        self.profile.weight_kg = None
        self.profile.save()
        response = self.client.get(reverse("nutrition:dashboard"))
        self.assertContains(response, "Complete your profile")

    def test_dashboard_reflects_logged_meal_totals(self):
        MealEntry.objects.create(user=self.user, food=self.food, meal_category="lunch", quantity=2)
        response = self.client.get(reverse("nutrition:dashboard"))
        self.assertEqual(response.context["totals"]["calories"], 330)


class FoodSearchAndLoggingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "athlete@example.com", "password123!")
        self.client.login(username="athlete", password="password123!")
        self.food = Food.objects.create(
            name="Oats", serving_size=40, serving_unit="g",
            calories=150, protein_g=5.3, carbs_g=27, fat_g=2.7,
        )
        Food.objects.create(
            name="Other user's food", serving_size=100, serving_unit="g",
            calories=100, protein_g=1, carbs_g=1, fat_g=1,
            created_by=User.objects.create_user("other", "other@example.com", "password123!"),
        )

    def test_search_finds_matching_food_but_not_other_users_custom_food(self):
        response = self.client.get(reverse("nutrition:food_search"), {"q": "oat"})
        names = [f.name for f in response.context["results"]]
        self.assertIn("Oats", names)
        self.assertEqual(len(names), 1)

    def test_add_meal_entry_snapshots_nutrition_and_scales_by_quantity(self):
        response = self.client.post(
            reverse("nutrition:add_meal_entry", args=[self.food.id]),
            {"meal_category": "breakfast", "quantity": "2"},
        )
        self.assertRedirects(response, reverse("nutrition:dashboard"))
        entry = MealEntry.objects.get(user=self.user, food=self.food)
        self.assertEqual(entry.calories, 300)
        self.assertEqual(entry.protein_g, 10.6)

    def test_meal_entry_edit_rescales_snapshot(self):
        entry = MealEntry.objects.create(user=self.user, food=self.food, meal_category="breakfast", quantity=1)
        self.client.post(
            reverse("nutrition:meal_entry_edit", args=[entry.id]),
            {"meal_category": "breakfast", "quantity": "3"},
        )
        entry.refresh_from_db()
        self.assertEqual(entry.calories, 450)

    def test_cannot_edit_another_users_meal_entry(self):
        other = User.objects.create_user("intruder", "intruder@example.com", "password123!")
        entry = MealEntry.objects.create(user=other, food=self.food, meal_category="breakfast", quantity=1)
        response = self.client.post(
            reverse("nutrition:meal_entry_edit", args=[entry.id]),
            {"meal_category": "lunch", "quantity": "1"},
        )
        self.assertEqual(response.status_code, 404)

    def test_meal_entry_delete_removes_only_own_entry(self):
        entry = MealEntry.objects.create(user=self.user, food=self.food, meal_category="snack", quantity=1)
        self.client.post(reverse("nutrition:meal_entry_delete", args=[entry.id]))
        self.assertFalse(MealEntry.objects.filter(id=entry.id).exists())


class WaterAndStepTrackerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "athlete@example.com", "password123!")
        self.client.login(username="athlete", password="password123!")

    def test_water_quick_add_uses_profile_serving_size(self):
        self.client.post(reverse("nutrition:water_add"))
        log = WaterLog.objects.get(user=self.user)
        self.assertEqual(log.amount_ml, self.user.profile.water_serving_ml)

    def test_water_custom_amount(self):
        self.client.post(reverse("nutrition:water_add"), {"amount_ml": "500"})
        log = WaterLog.objects.get(user=self.user)
        self.assertEqual(log.amount_ml, 500)

    def test_water_delete_removes_only_own_log(self):
        other = User.objects.create_user("other", "other2@example.com", "password123!")
        other_log = WaterLog.objects.create(user=other, amount_ml=250)
        response = self.client.post(reverse("nutrition:water_delete", args=[other_log.id]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(WaterLog.objects.filter(id=other_log.id).exists())

    def test_step_set_creates_then_updates_todays_entry(self):
        self.client.post(reverse("nutrition:step_set"), {"step_count": "4000"})
        self.client.post(reverse("nutrition:step_set"), {"step_count": "9000"})
        today = timezone.localdate()
        self.assertEqual(StepLog.objects.filter(user=self.user, date=today).count(), 1)
        self.assertEqual(StepLog.objects.get(user=self.user, date=today).step_count, 9000)


def _gemini_envelope(raw_items):
    import json

    return {"candidates": [{"content": {"parts": [{"text": json.dumps(raw_items)}]}}]}


class GeminiClientTests(TestCase):
    def test_raises_configuration_error_without_api_key(self):
        with self.assertRaises(GeminiConfigurationError):
            parse_food_description("an apple", api_key="")

    def test_raises_on_blank_description(self):
        with self.assertRaises(GeminiResponseError):
            parse_food_description("   ", api_key="test-key")

    @patch("nutrition.ai_client._call_gemini")
    def test_happy_path_returns_validated_items(self, mock_call):
        mock_call.return_value = _gemini_envelope(
            [
                {
                    "name": "Apple",
                    "quantity": 1,
                    "unit": "medium",
                    "meal_category": "snack",
                    "calories": 95,
                    "protein_g": 0.5,
                    "carbs_g": 25,
                    "fat_g": 0.3,
                }
            ]
        )
        items = parse_food_description("an apple", api_key="test-key")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].name, "Apple")
        self.assertEqual(items[0].calories, 95)

    @patch("nutrition.ai_client._call_gemini")
    def test_items_missing_required_fields_are_dropped(self, mock_call):
        mock_call.return_value = _gemini_envelope(
            [{"name": "Mystery food", "quantity": 1, "unit": "serving"}]
        )
        with self.assertRaises(GeminiResponseError):
            parse_food_description("something", api_key="test-key")

    @patch("nutrition.ai_client._call_gemini")
    def test_partial_batch_keeps_only_valid_items(self, mock_call):
        mock_call.return_value = _gemini_envelope(
            [
                {"name": "Mystery food", "quantity": 1, "unit": "serving"},
                {
                    "name": "Banana",
                    "quantity": 1,
                    "unit": "medium",
                    "meal_category": "snack",
                    "calories": 105,
                    "protein_g": 1.3,
                    "carbs_g": 27,
                    "fat_g": 0.4,
                },
            ]
        )
        items = parse_food_description("stuff", api_key="test-key")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].name, "Banana")

    @patch("nutrition.ai_client._call_gemini")
    def test_empty_description_in_items_returns_empty_list(self, mock_call):
        mock_call.return_value = _gemini_envelope([])
        items = parse_food_description("just water", api_key="test-key")
        self.assertEqual(items, [])

    @patch("nutrition.ai_client._call_gemini", side_effect=GeminiRequestError("down"))
    def test_network_failure_propagates_as_gemini_request_error(self, mock_call):
        with self.assertRaises(GeminiRequestError):
            parse_food_description("an apple", api_key="test-key")

    def test_malformed_envelope_raises_response_error(self):
        with patch("nutrition.ai_client._call_gemini", return_value={"candidates": []}):
            with self.assertRaises(GeminiResponseError):
                parse_food_description("an apple", api_key="test-key")


class AIRateLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "athlete@example.com", "password123!")

    def test_remaining_decreases_with_use(self):
        self.assertEqual(requests_remaining_today(self.user), 20)
        record_attempt_or_raise(self.user)
        self.assertEqual(requests_remaining_today(self.user), 19)

    @override_settings(GEMINI_DAILY_LIMIT=2)
    def test_raises_once_daily_limit_is_reached(self):
        record_attempt_or_raise(self.user)
        record_attempt_or_raise(self.user)
        with self.assertRaises(RateLimitExceeded):
            record_attempt_or_raise(self.user)
        self.assertEqual(AIFoodLogRequest.objects.filter(user=self.user).count(), 2)


@override_settings(GEMINI_API_KEY="test-key")
class AIFoodLogViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "athlete@example.com", "password123!")
        self.client.login(username="athlete", password="password123!")

    @override_settings(GEMINI_API_KEY="")
    def test_form_shows_disabled_message_without_api_key(self):
        response = self.client.get(reverse("nutrition:ai_food_log"))
        self.assertContains(response, "isn't configured")

    def test_blank_description_shows_error_and_does_not_call_gemini(self):
        with patch("nutrition.views.parse_food_description") as mock_parse:
            response = self.client.post(reverse("nutrition:ai_food_log"), {"description": ""}, follow=True)
        mock_parse.assert_not_called()
        self.assertContains(response, "Describe what you ate")

    def test_gemini_error_shows_message_and_redirects_back(self):
        with patch("nutrition.views.parse_food_description", side_effect=GeminiResponseError("bad output")):
            response = self.client.post(
                reverse("nutrition:ai_food_log"), {"description": "an apple"}, follow=True
            )
        self.assertContains(response, "bad output")

    def test_successful_parse_redirects_to_review(self):
        from .ai_client import ParsedFoodItem

        item = ParsedFoodItem(
            name="Apple", quantity=1, unit="medium", meal_category="snack",
            calories=95, protein_g=0.5, carbs_g=25, fat_g=0.3,
        )
        with patch("nutrition.views.parse_food_description", return_value=[item]):
            response = self.client.post(reverse("nutrition:ai_food_log"), {"description": "an apple"})
        self.assertRedirects(response, reverse("nutrition:ai_food_log_review"))
        self.assertEqual(self.client.session[views_module.AI_SESSION_KEY][0]["name"], "Apple")

    def test_rate_limit_exceeded_blocks_call_to_gemini(self):
        for _ in range(20):
            AIFoodLogRequest.objects.create(user=self.user)
        with patch("nutrition.views.parse_food_description") as mock_parse:
            response = self.client.post(
                reverse("nutrition:ai_food_log"), {"description": "an apple"}, follow=True
            )
        mock_parse.assert_not_called()
        self.assertContains(response, "limit")

    def test_review_without_session_data_redirects_to_form(self):
        response = self.client.get(reverse("nutrition:ai_food_log_review"), follow=True)
        self.assertRedirects(response, reverse("nutrition:ai_food_log"))

    def test_confirming_review_creates_food_and_meal_entry(self):
        session = self.client.session
        session[views_module.AI_SESSION_KEY] = [
            {
                "name": "Apple", "quantity": 1, "unit": "medium", "meal_category": "snack",
                "calories": 95, "protein_g": 0.5, "carbs_g": 25, "fat_g": 0.3,
            }
        ]
        session.save()

        response = self.client.post(
            reverse("nutrition:ai_food_log_review"),
            {"include_0": "on", "meal_category_0": "breakfast", "multiplier_0": "2"},
        )
        self.assertRedirects(response, reverse("nutrition:dashboard"))

        entry = MealEntry.objects.get(user=self.user)
        self.assertEqual(entry.food.name, "Apple")
        self.assertEqual(entry.meal_category, "breakfast")
        self.assertEqual(entry.quantity, 2)
        self.assertEqual(entry.calories, 190)
        self.assertNotIn(views_module.AI_SESSION_KEY, self.client.session)

    def test_unchecking_an_item_does_not_log_it(self):
        session = self.client.session
        session[views_module.AI_SESSION_KEY] = [
            {
                "name": "Apple", "quantity": 1, "unit": "medium", "meal_category": "snack",
                "calories": 95, "protein_g": 0.5, "carbs_g": 25, "fat_g": 0.3,
            }
        ]
        session.save()

        self.client.post(reverse("nutrition:ai_food_log_review"), {})
        self.assertFalse(MealEntry.objects.filter(user=self.user).exists())
