"""Utilities for generating scheduled class sessions from weekly patterns."""

from datetime import timedelta


def iter_scheduled_session_dates(start_date, end_date, weekdays):
    """
    Yield session dates between ``start_date`` and ``end_date`` inclusive.

    ``weekdays`` uses Python's ``date.weekday()`` convention (Monday=0, Sunday=6).
    """
    weekday_set = set(weekdays)
    if not weekday_set:
        return

    current = start_date
    while current <= end_date:
        if current.weekday() in weekday_set:
            yield current
        current += timedelta(days=1)


def build_session_plan(start_date, end_date, weekdays):
    """Return ordered ``(session_number, session_date)`` pairs for a class schedule."""
    return [
        (index, session_date)
        for index, session_date in enumerate(
            iter_scheduled_session_dates(start_date, end_date, weekdays),
            start=1,
        )
    ]
