"""XP and leveling: a simple, predictable reward layer on top of badges
and challenges. XP is append-only (XPEvent rows) so the total is always
reconstructable and never silently adjusted.
"""

from django.db.models import Sum

from .models import XPEvent

XP_PER_COMPLETED_WORKOUT = 10
XP_PER_BADGE = 25
LEVEL_XP_STEP = 100


def award_xp(user, amount, reason):
    if amount <= 0:
        return
    XPEvent.objects.create(user=user, amount=amount, reason=reason)


def total_xp(user):
    return XPEvent.objects.filter(user=user).aggregate(total=Sum("amount"))["total"] or 0


def level_progress(user):
    """Current level and progress toward the next one.

    Leveling is a flat `LEVEL_XP_STEP` XP per level - simple and
    predictable rather than a curve, since the point is steady positive
    feedback, not a long grind.
    """
    xp = total_xp(user)
    level = xp // LEVEL_XP_STEP + 1
    xp_into_level = xp % LEVEL_XP_STEP
    return {
        "xp": xp,
        "level": level,
        "xp_into_level": xp_into_level,
        "xp_for_next_level": LEVEL_XP_STEP,
        "pct_to_next_level": round(xp_into_level / LEVEL_XP_STEP * 100),
    }
