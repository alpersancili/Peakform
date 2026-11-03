"""Conversational AI coach via the Google Gemini API.

Unlike nutrition.ai_client (which forces a strict JSON schema for food
parsing), this is free-form text - the coach is meant to explain things
in plain language. What keeps it honest is the system prompt plus
coach.context.build_user_context: the model is explicitly told to
reason only from the real data it's handed and to ask rather than
guess, never to invent numbers, and never to diagnose medical
conditions or promise specific results.
"""

import json
import urllib.error
import urllib.request

from django.conf import settings

MAX_MESSAGE_LENGTH = 1500
GEMINI_ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)
REQUEST_TIMEOUT_SECONDS = 20
MAX_HISTORY_TURNS = 10  # most recent user+assistant messages included for context

SYSTEM_PROMPT = """You are Peakform's AI fitness coach, talking directly to one user inside their fitness app.

You will be given a factual snapshot of this user's real profile, nutrition targets and logs, workout plan and history, streak, and progress data. Treat that snapshot as ground truth and reason only from it - never invent numbers, workouts, or history that weren't given to you. If you need information that isn't in the snapshot or the conversation to answer well, ask the user for it instead of guessing.

Rules:
- Explain your reasoning in plain, encouraging language a beginner can follow.
- Never diagnose medical conditions, and never present your advice as a substitute for a doctor, physical therapist, or registered dietitian - if the user mentions pain, injury, illness, or disordered eating patterns, clearly recommend they consult a qualified professional instead of (or in addition to) answering.
- Never promise a specific result or timeline ("you'll gain 2kg by next month").
- Keep a consistency-focused, non-judgmental tone - a missed workout or an off-target day is normal, not a failure.
- Keep responses focused and practical, not walls of text.
- Write in plain text only - no markdown (no **bold**, no bullet/numbered list syntax, no headings). The chat interface displays your text exactly as written, so markdown symbols would show up as literal asterisks and dashes instead of formatting. Use plain sentences and paragraphs, or simple line breaks for a short list.
"""


class CoachError(Exception):
    """Base class for all errors raised by this module."""


class CoachConfigurationError(CoachError):
    """Raised when the API key is missing, so the caller can degrade gracefully."""


class CoachRequestError(CoachError):
    """Raised on network failure or a non-success HTTP response."""


class CoachResponseError(CoachError):
    """Raised when Gemini's response can't be parsed into a reply."""


def _call_gemini(payload, *, api_key, model):
    """Issue the HTTP request to Gemini. Isolated so tests can mock it."""
    url = GEMINI_ENDPOINT_TEMPLATE.format(model=model, key=api_key)
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise CoachRequestError(f"Gemini API returned HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise CoachRequestError("Could not reach the Gemini API.") from exc
    except json.JSONDecodeError as exc:
        raise CoachResponseError("Gemini API response was not valid JSON.") from exc


def _extract_text(envelope):
    try:
        candidates = envelope["candidates"]
        if not candidates:
            raise CoachResponseError("Gemini returned no candidates.")
        return candidates[0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise CoachResponseError("Gemini response was missing expected fields.") from exc


def send_coach_message(message, *, user_context, history, api_key=None, model=None):
    """Send a message to the AI coach and return its reply text.

    `history` is a list of CoachMessage-like objects (role, content) in
    chronological order, NOT including the new `message` - only the most
    recent MAX_HISTORY_TURNS are actually sent, to keep the request a
    reasonable size.
    """
    api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
    if not api_key:
        raise CoachConfigurationError("The AI coach is not configured on this server.")

    message = (message or "").strip()
    if not message:
        raise CoachResponseError("Please enter a message.")
    message = message[:MAX_MESSAGE_LENGTH]

    model = model or getattr(settings, "GEMINI_MODEL", "gemini-3.1-flash-lite")

    turns = []
    for past in history[-MAX_HISTORY_TURNS:]:
        role = "model" if past.role == "assistant" else "user"
        turns.append({"role": role, "parts": [{"text": past.content}]})
    turns.append({"role": "user", "parts": [{"text": f"User data snapshot:\n{user_context}\n\nUser's message: {message}"}]})

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": turns,
    }

    envelope = _call_gemini(payload, api_key=api_key, model=model)
    text = _extract_text(envelope)
    if not text or not text.strip():
        raise CoachResponseError("Gemini returned an empty reply.")
    return text.strip()
