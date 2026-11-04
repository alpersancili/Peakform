"""Previous-session performance lookup.

Logging a set from a blank form means guessing at what you did last
time. This finds the matching set from the most recent earlier
*completed* session that logged the same exercise, so the session page
can show it and pre-fill the next set's input with it.
"""

from .models import ExerciseLog, SessionStatus


def previous_session_set_map(user, exercise, exclude_session_id):
    """set_number -> ExerciseLog from the last earlier completed session
    that logged this exercise, or {} if there isn't one.
    """
    previous_session_id = (
        ExerciseLog.objects.filter(
            session__user=user,
            session__status=SessionStatus.COMPLETED,
            exercise=exercise,
        )
        .exclude(session_id=exclude_session_id)
        .order_by("-session__date", "-session__started_at")
        .values_list("session_id", flat=True)
        .first()
    )
    if not previous_session_id:
        return {}
    return {
        log.set_number: log
        for log in ExerciseLog.objects.filter(session_id=previous_session_id, exercise=exercise)
    }


def previous_session_totals(user, exercise, exclude_session_id):
    """(total_reps, total_hold_seconds) summed over the most recent earlier
    completed session that logged this exercise, or (None, None) if there
    isn't one. Either total is None if that movement type doesn't apply.
    """
    logs = previous_session_set_map(user, exercise, exclude_session_id).values()
    if not logs:
        return None, None
    total_reps = sum(log.reps for log in logs if log.reps) or None
    total_hold_seconds = sum(log.hold_seconds for log in logs if log.hold_seconds) or None
    return total_reps, total_hold_seconds
