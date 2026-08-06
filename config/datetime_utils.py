import calendar
from datetime import date, datetime, time, timedelta

from django.utils import timezone


def calendar_month_range(year: int, month: int) -> tuple[date, date]:
    """Return the first and last day of a Gregorian calendar month."""
    start = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end = date(year, month, last_day)
    return start, end


def session_salary_deadline(session_date: date) -> datetime:
    """Reports must be approved within 48 hours of the session date."""
    naive = datetime.combine(session_date, time.min) + timedelta(hours=48)
    return timezone.make_aware(naive, timezone.get_current_timezone())


def is_salary_eligible(session_date: date, approved_at: datetime) -> bool:
    return approved_at <= session_salary_deadline(session_date)
