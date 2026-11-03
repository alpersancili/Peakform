from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import ActivityLevel, ExperienceLevel, PrimaryGoal, Sex

from .ai_client import (
    CoachConfigurationError,
    CoachRequestError,
    CoachResponseError,
    send_coach_message,
)
from .context import build_user_context
from .models import CoachMessage, CoachRequest, MessageRole
from .rate_limit import RateLimitExceeded, record_attempt_or_raise, requests_remaining_today


def _gemini_envelope(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


class CoachAiClientTests(TestCase):
    def test_raises_configuration_error_without_api_key(self):
        with self.assertRaises(CoachConfigurationError):
            send_coach_message("hi", user_context="ctx", history=[], api_key="")

    def test_raises_on_blank_message(self):
        with self.assertRaises(CoachResponseError):
            send_coach_message("   ", user_context="ctx", history=[], api_key="test-key")

    @patch("coach.ai_client._call_gemini")
    def test_happy_path_returns_reply_text(self, mock_call):
        mock_call.return_value = _gemini_envelope("Eat more protein today.")
        reply = send_coach_message("What should I eat?", user_context="ctx", history=[], api_key="test-key")
        self.assertEqual(reply, "Eat more protein today.")

    @patch("coach.ai_client._call_gemini")
    def test_history_included_as_prior_turns(self, mock_call):
        mock_call.return_value = _gemini_envelope("Sure, here's a follow-up.")

        class FakeMsg:
            def __init__(self, role, content):
                self.role = role
                self.content = content

        history = [FakeMsg(MessageRole.USER, "hi"), FakeMsg(MessageRole.ASSISTANT, "hello")]
        send_coach_message("follow up", user_context="ctx", history=history, api_key="test-key")
        payload = mock_call.call_args[0][0]
        roles = [turn["role"] for turn in payload["contents"]]
        self.assertEqual(roles, ["user", "model", "user"])

    @patch("coach.ai_client._call_gemini", side_effect=CoachRequestError("down"))
    def test_network_failure_propagates(self, mock_call):
        with self.assertRaises(CoachRequestError):
            send_coach_message("hi", user_context="ctx", history=[], api_key="test-key")

    def test_empty_reply_raises_response_error(self):
        with patch("coach.ai_client._call_gemini", return_value=_gemini_envelope("   ")):
            with self.assertRaises(CoachResponseError):
                send_coach_message("hi", user_context="ctx", history=[], api_key="test-key")


class CoachRateLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "athlete@example.com", "password123!")

    def test_remaining_decreases_with_use(self):
        self.assertEqual(requests_remaining_today(self.user), 30)
        record_attempt_or_raise(self.user)
        self.assertEqual(requests_remaining_today(self.user), 29)

    @override_settings(COACH_DAILY_LIMIT=2)
    def test_raises_once_daily_limit_reached(self):
        record_attempt_or_raise(self.user)
        record_attempt_or_raise(self.user)
        with self.assertRaises(RateLimitExceeded):
            record_attempt_or_raise(self.user)
        self.assertEqual(CoachRequest.objects.filter(user=self.user).count(), 2)


class CoachContextTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "athlete@example.com", "password123!")

    def test_context_notes_incomplete_profile(self):
        context = build_user_context(self.user)
        self.assertIn("incomplete", context)

    def test_context_includes_real_profile_data(self):
        import datetime

        profile = self.user.profile
        profile.height_cm = 178
        profile.weight_kg = 75
        profile.date_of_birth = datetime.date(1997, 6, 1)
        profile.sex = Sex.MALE
        profile.activity_level = ActivityLevel.MODERATE
        profile.experience_level = ExperienceLevel.INTERMEDIATE
        profile.primary_goal = PrimaryGoal.MUSCLE_GAIN
        profile.save()

        context = build_user_context(self.user)
        self.assertIn("178cm", context)
        self.assertIn("75.0kg", context)
        self.assertIn("Muscle gain", context)
        self.assertIn("Nutrition targets:", context)

    def test_context_stays_within_size_budget(self):
        context = build_user_context(self.user)
        self.assertLessEqual(len(context), 3000)


@override_settings(GEMINI_API_KEY="test-key")
class CoachChatViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "athlete@example.com", "password123!")
        self.client.login(username="athlete", password="password123!")

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("coach:chat"))
        self.assertEqual(response.status_code, 302)

    @override_settings(GEMINI_API_KEY="")
    def test_shows_disabled_message_without_api_key(self):
        response = self.client.get(reverse("coach:chat"))
        self.assertContains(response, "isn't configured")

    def test_blank_message_shows_error_and_does_not_call_gemini(self):
        with patch("coach.views.send_coach_message") as mock_send:
            response = self.client.post(reverse("coach:chat"), {"message": ""}, follow=True)
        mock_send.assert_not_called()
        self.assertContains(response, "Please enter a message")

    def test_successful_message_is_saved_both_sides(self):
        with patch("coach.views.send_coach_message", return_value="Here's a plan for you."):
            self.client.post(reverse("coach:chat"), {"message": "Help me plan today"})
        messages = list(CoachMessage.objects.filter(user=self.user).order_by("created_at"))
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].role, MessageRole.USER)
        self.assertEqual(messages[0].content, "Help me plan today")
        self.assertEqual(messages[1].role, MessageRole.ASSISTANT)
        self.assertEqual(messages[1].content, "Here's a plan for you.")

    def test_gemini_error_shows_message_and_does_not_save(self):
        with patch("coach.views.send_coach_message", side_effect=CoachResponseError("bad output")):
            response = self.client.post(reverse("coach:chat"), {"message": "hi"}, follow=True)
        self.assertContains(response, "bad output")
        self.assertFalse(CoachMessage.objects.filter(user=self.user).exists())

    def test_rate_limit_exceeded_blocks_call_to_gemini(self):
        for _ in range(30):
            CoachRequest.objects.create(user=self.user)
        with patch("coach.views.send_coach_message") as mock_send:
            response = self.client.post(reverse("coach:chat"), {"message": "hi"}, follow=True)
        mock_send.assert_not_called()
        self.assertContains(response, "limit")

    def test_another_users_messages_are_not_shown(self):
        other = User.objects.create_user("other", "other@example.com", "password123!")
        CoachMessage.objects.create(user=other, role=MessageRole.USER, content="secret question")
        response = self.client.get(reverse("coach:chat"))
        self.assertNotContains(response, "secret question")

    def test_conversation_history_passed_to_gemini_in_order(self):
        CoachMessage.objects.create(user=self.user, role=MessageRole.USER, content="first")
        CoachMessage.objects.create(user=self.user, role=MessageRole.ASSISTANT, content="first reply")
        with patch("coach.views.send_coach_message", return_value="second reply") as mock_send:
            self.client.post(reverse("coach:chat"), {"message": "second"})
        history_arg = mock_send.call_args.kwargs["history"]
        self.assertEqual([m.content for m in history_arg], ["first", "first reply"])

    def test_clear_conversation_removes_only_this_users_messages(self):
        other = User.objects.create_user("other", "other@example.com", "password123!")
        CoachMessage.objects.create(user=self.user, role=MessageRole.USER, content="mine")
        CoachMessage.objects.create(user=other, role=MessageRole.USER, content="not mine")
        self.client.post(reverse("coach:clear_conversation"))
        self.assertFalse(CoachMessage.objects.filter(user=self.user).exists())
        self.assertTrue(CoachMessage.objects.filter(user=other).exists())
