from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .ai_client import CoachConfigurationError, CoachError, send_coach_message
from .context import build_user_context
from .forms import CoachMessageForm
from .models import CoachMessage, MessageRole
from .rate_limit import RateLimitExceeded, record_attempt_or_raise, requests_remaining_today


@login_required
def chat(request):
    configured = bool(settings.GEMINI_API_KEY)

    if request.method == "POST":
        if not configured:
            messages.error(request, "The AI coach isn't configured on this server yet.")
            return redirect("coach:chat")

        form = CoachMessageForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Please enter a message.")
            return redirect("coach:chat")

        try:
            record_attempt_or_raise(request.user)
        except RateLimitExceeded as exc:
            minutes = max(1, int(exc.retry_after.total_seconds() // 60))
            messages.error(request, f"You've hit today's AI coach limit. Try again in about {minutes} minutes.")
            return redirect("coach:chat")

        user_message = form.cleaned_data["message"]
        history = list(CoachMessage.objects.filter(user=request.user).order_by("created_at"))
        user_context = build_user_context(request.user)

        try:
            reply = send_coach_message(user_message, user_context=user_context, history=history)
        except CoachConfigurationError:
            messages.error(request, "The AI coach isn't configured on this server yet.")
            return redirect("coach:chat")
        except CoachError as exc:
            messages.error(request, str(exc))
            return redirect("coach:chat")

        CoachMessage.objects.create(user=request.user, role=MessageRole.USER, content=user_message)
        CoachMessage.objects.create(user=request.user, role=MessageRole.ASSISTANT, content=reply)
        return redirect("coach:chat")

    conversation = CoachMessage.objects.filter(user=request.user).order_by("created_at")
    return render(
        request,
        "coach/chat.html",
        {
            "configured": configured,
            "conversation": conversation,
            "form": CoachMessageForm(),
            "remaining_today": requests_remaining_today(request.user),
        },
    )


@login_required
def clear_conversation(request):
    if request.method == "POST":
        CoachMessage.objects.filter(user=request.user).delete()
        messages.success(request, "Conversation cleared.")
    return redirect("coach:chat")
