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
