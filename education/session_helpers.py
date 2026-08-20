"""Helpers to ensure class sessions exist for scheduled classes."""

from education.models import ClassRoom


def ensure_classroom_sessions(classroom: ClassRoom) -> int:
    """
    Generate session slots when weekdays are configured but sessions are missing.

    Returns the number of active sessions after ensuring the schedule exists.
    """
    weekday_count = classroom.weekdays.filter(is_deleted=False).count()
    if weekday_count == 0:
        return 0

    session_count = classroom.sessions.filter(is_deleted=False).count()
    if session_count == 0:
        classroom.regenerate_sessions()
        session_count = classroom.sessions.filter(is_deleted=False).count()
    return session_count
