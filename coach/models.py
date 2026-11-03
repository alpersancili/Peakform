from django.conf import settings
from django.db import models


class MessageRole(models.TextChoices):
    USER = "user", "User"
    ASSISTANT = "assistant", "Assistant"


class CoachMessage(models.Model):
    """One turn in a user's conversation with the AI coach.

    Stored per-user (not per-conversation) - the coach is a single
    ongoing conversation per user, not multiple named threads, which
    keeps this simple while still giving genuine multi-turn context.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coach_messages")
    role = models.CharField(max_length=10, choices=MessageRole.choices)
    content = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user} ({self.role}): {self.content[:40]}"


class CoachRequest(models.Model):
    """One attempted call to the AI coach, for rate limiting.

    Recorded before the Gemini call is made (not just on success), same
    reasoning as nutrition.models.AIFoodLogRequest: a user can't bypass
    the daily limit by sending messages designed to fail.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coach_requests")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
