"""Natural-language food logging via the Google Gemini API.

Gemini is asked to turn a free-text description (e.g. "two eggs and a
slice of toast with butter") into a structured list of food items with
estimated nutrition. Nothing here is treated as trustworthy by default:
the raw model response is validated field-by-field before it is allowed
anywhere near the database, and a malformed or unreachable API never
raises past this module as anything but one of the typed errors below.
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from django.conf import settings

from .models import MealCategory

GEMINI_ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)

MAX_DESCRIPTION_LENGTH = 1000
MAX_ITEM_CALORIES = 5000
MAX_ITEM_QUANTITY = 100
REQUEST_TIMEOUT_SECONDS = 15

VALID_MEAL_CATEGORIES = {choice for choice, _ in MealCategory.choices}

RESPONSE_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING"},
            "quantity": {"type": "NUMBER"},
            "unit": {"type": "STRING"},
            "meal_category": {"type": "STRING", "enum": sorted(VALID_MEAL_CATEGORIES)},
            "calories": {"type": "NUMBER"},
            "protein_g": {"type": "NUMBER"},
            "carbs_g": {"type": "NUMBER"},
            "fat_g": {"type": "NUMBER"},
        },
        "required": ["name", "quantity", "unit", "calories", "protein_g", "carbs_g", "fat_g"],
    },
}

PROMPT_INSTRUCTIONS = (
    "You are a nutrition estimation assistant for a fitness app. The user will "
    "describe, in their own words, food they ate. Break their description into "
    "one entry per distinct food item, and for each one estimate reasonable "
    "nutrition values for the quantity described. `quantity` is a numeric "
    "multiplier of one serving of `unit` (e.g. quantity=2, unit='egg'). Guess "
    "`meal_category` from context (breakfast/lunch/dinner/snack); default to "
    "'snack' if genuinely unclear. All nutrition fields are totals for the "
    "quantity described, in kilocalories and grams. If the description does "
    "not mention any food, return an empty array.\n\nDescription: "
)


class GeminiError(Exception):
    """Base class for all errors raised by this module."""


class GeminiConfigurationError(GeminiError):
    """Raised when the API key is missing, so the caller can degrade gracefully."""


class GeminiRequestError(GeminiError):
    """Raised on network failure or a non-success HTTP response."""


class GeminiResponseError(GeminiError):
    """Raised when Gemini's response cannot be parsed into valid food items."""


@dataclass
class ParsedFoodItem:
    name: str
    quantity: float
    unit: str
    meal_category: str
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float


def _call_gemini(prompt, *, api_key, model):
    """Issue the HTTP request to Gemini. Isolated so tests can mock it."""
    url = GEMINI_ENDPOINT_TEMPLATE.format(model=model, key=api_key)
    body = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": RESPONSE_SCHEMA,
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise GeminiRequestError(f"Gemini API returned HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise GeminiRequestError("Could not reach the Gemini API.") from exc
    except json.JSONDecodeError as exc:
        raise GeminiResponseError("Gemini API response was not valid JSON.") from exc


def _extract_text(envelope):
    try:
        candidates = envelope["candidates"]
        if not candidates:
            raise GeminiResponseError("Gemini returned no candidates.")
        return candidates[0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise GeminiResponseError("Gemini response was missing expected fields.") from exc


def _coerce_positive_number(value, maximum):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number < 0 or number > maximum:  # NaN check via self-inequality
        return None
    return number


def _validate_item(raw):
    """Return a ParsedFoodItem for a well-formed raw dict, else None."""
    if not isinstance(raw, dict):
        return None

    name = str(raw.get("name", "")).strip()[:150]
    if not name:
        return None

    quantity = _coerce_positive_number(raw.get("quantity"), MAX_ITEM_QUANTITY)
    if quantity is None or quantity <= 0:
        return None

    unit = str(raw.get("unit", "serving")).strip()[:20] or "serving"

    meal_category = str(raw.get("meal_category", "")).strip().lower()
    if meal_category not in VALID_MEAL_CATEGORIES:
        meal_category = MealCategory.SNACK

    nutrition = {}
    for field in ("calories", "protein_g", "carbs_g", "fat_g"):
        value = _coerce_positive_number(raw.get(field), MAX_ITEM_CALORIES)
        if value is None:
            return None
        nutrition[field] = value

    return ParsedFoodItem(name=name, quantity=quantity, unit=unit, meal_category=meal_category, **nutrition)


def parse_food_description(description, *, api_key=None, model=None):
    """Turn a free-text food description into a list of ParsedFoodItem.

    Raises GeminiConfigurationError, GeminiRequestError, or
    GeminiResponseError; never returns a partially-validated item.
    """
    api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
    if not api_key:
        raise GeminiConfigurationError("The AI assistant is not configured on this server.")

    description = (description or "").strip()
    if not description:
        raise GeminiResponseError("Please describe what you ate.")
    description = description[:MAX_DESCRIPTION_LENGTH]

    model = model or getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")
    prompt = PROMPT_INSTRUCTIONS + description

    envelope = _call_gemini(prompt, api_key=api_key, model=model)
    text = _extract_text(envelope)

    try:
        raw_items = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GeminiResponseError("Gemini's response was not valid JSON.") from exc

    if not isinstance(raw_items, list):
        raise GeminiResponseError("Gemini's response was not a list of food items.")

    items = [item for item in (_validate_item(raw) for raw in raw_items) if item is not None]
    if raw_items and not items:
        raise GeminiResponseError("Couldn't understand any food items in Gemini's response.")
    return items
