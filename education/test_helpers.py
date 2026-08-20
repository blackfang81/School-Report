"""Shared helpers for education and report tests."""

from datetime import date, timedelta

from education.models import ClassRoom, ClassRoomWeekday, ClassSession, TeacherAssignment, Weekday


def create_classroom_with_schedule(
    *,
    school,
    term,
    teacher=None,
    weekdays=None,
    name="Class A",
    session_duration=90,
    start_date=None,
    end_date=None,
):
    """Create a class with weekdays and generated sessions."""
    if weekdays is None:
        weekdays = [Weekday.SUNDAY, Weekday.WEDNESDAY]
    if start_date is None:
        start_date = term.start_date
    if end_date is None:
        end_date = term.end_date

    classroom = ClassRoom.objects.create(
        school=school,
        term=term,
        name=name,
        session_duration=session_duration,
        start_date=start_date,
        end_date=end_date,
    )
    for weekday in weekdays:
        ClassRoomWeekday.objects.create(classroom=classroom, weekday=weekday)
    classroom.regenerate_sessions()

    if teacher is not None:
        TeacherAssignment.objects.create(
            classroom=classroom,
            teacher=teacher,
            start_date=start_date,
        )

    return classroom


def create_classroom_with_session_dates(
    *,
    school,
    term,
    teacher=None,
    session_dates,
    name="Class A",
    session_duration=90,
):
    """Create a class with explicit session dates (for deterministic tests)."""
    start_date = min(session_dates)
    end_date = max(session_dates)
    classroom = ClassRoom.objects.create(
        school=school,
        term=term,
        name=name,
        session_duration=session_duration,
        start_date=start_date,
        end_date=end_date,
    )
    for index, session_date in enumerate(session_dates, start=1):
        ClassSession.objects.create(
            classroom=classroom,
            session_number=index,
            session_date=session_date,
        )
    if teacher is not None:
        TeacherAssignment.objects.create(
            classroom=classroom,
            teacher=teacher,
            start_date=start_date,
        )
    return classroom


def january_2026_dates(count, start_day=1):
    """Return ``count`` consecutive dates in January 2026."""
    start = date(2026, 1, start_day)
    return [start + timedelta(days=offset) for offset in range(count)]

