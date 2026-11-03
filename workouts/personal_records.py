"""Personal-best tracking for calisthenics exercises.

There's no weight to track in bodyweight training, so a "personal record"
is the best single set ever logged for an exercise: most reps for a
rep-based movement, or longest hold for a timed one. Only sets logged in
a *completed* session count, so an in-progress session can't contribute
a PR before the user actually finishes it.
"""

from .models import ExerciseLog, MovementType, SessionStatus


def _set_metric(log):
    """The comparable number for one logged set, or None if it can't be compared."""
    if log.exercise.movement_type == MovementType.HOLD:
        return log.hold_seconds
    return log.reps


def compute_personal_records(user):
    """One best-ever entry per exercise the user has completed a set of.

    Returns a list of dicts (exercise, movement_type, value, date,
    session_id), sorted by exercise name. Ties are broken by the
    earliest date the value was first reached.
    """
    logs = (
        ExerciseLog.objects.filter(session__user=user, session__status=SessionStatus.COMPLETED)
        .select_related("exercise", "session")
        .order_by("session__date", "logged_at")
    )

    best_log_by_exercise = {}
    for log in logs:
        metric = _set_metric(log)
        if metric is None:
            continue
        current = best_log_by_exercise.get(log.exercise_id)
        if current is None or metric > _set_metric(current):
            best_log_by_exercise[log.exercise_id] = log

    records = [
        {
            "exercise": log.exercise,
            "movement_type": log.exercise.movement_type,
            "value": _set_metric(log),
            "date": log.session.date,
            "session_id": log.session_id,
        }
        for log in best_log_by_exercise.values()
    ]
    records.sort(key=lambda r: r["exercise"].name)
    return records


def detect_new_records(user, session):
    """Exercises where `session` set a new all-time best, as (exercise, value) pairs.

    Compares this session's best set per exercise against every other
    completed session's best, so call it any time after `session` has
    its sets logged (its own status doesn't matter, since it's excluded
    from the "previous" comparison set).
    """
    previous_best = {}
    previous_logs = (
        ExerciseLog.objects.filter(session__user=user, session__status=SessionStatus.COMPLETED)
        .exclude(session=session)
        .select_related("exercise")
    )
    for log in previous_logs:
        metric = _set_metric(log)
        if metric is None:
            continue
        if log.exercise_id not in previous_best or metric > previous_best[log.exercise_id]:
            previous_best[log.exercise_id] = metric

    session_best = {}
    for log in session.logs.select_related("exercise"):
        metric = _set_metric(log)
        if metric is None:
            continue
        current = session_best.get(log.exercise_id)
        if current is None or metric > current[1]:
            session_best[log.exercise_id] = (log.exercise, metric)

    new_records = [
        (exercise, value)
        for exercise_id, (exercise, value) in session_best.items()
        if value > previous_best.get(exercise_id, -1)
    ]
    new_records.sort(key=lambda pair: pair[0].name)
    return new_records
