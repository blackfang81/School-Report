import calendar
from datetime import date, datetime, time, timedelta

from django.utils import timezone


def calendar_month_range(year: int, month: int) -> tuple[date, date]:
    """Return the first and last day of a Gregorian calendar month."""
    start = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end = date(year, month, last_day)
    return start, end


def is_first_day_of_month(value: date) -> bool:
    """Return True when ``value`` is the first day of its month."""
    return value.day == 1


def is_last_day_of_month(value: date) -> bool:
    """Return True when ``value`` is the last day of its month."""
    return value.day == calendar.monthrange(value.year, value.month)[1]


def last_day_of_month(year: int, month: int) -> date:
    """Return the last calendar day for ``year``/``month``."""
    return date(year, month, calendar.monthrange(year, month)[1])


def payroll_period_for_calculation_date(calculation_date: date) -> tuple[date, date]:
    """
    Return the inclusive payroll ``(start, end)`` for a calculation run.

    The period is the 30 calendar days immediately before ``calculation_date``,
    ending the day before the calculation date.

    Example: calculating on 15 September covers 16 August through 14 September.
    """
    period_end = calculation_date - timedelta(days=1)
    period_start = calculation_date - timedelta(days=30)
    return period_start, period_end


def payroll_month_for_calculation_date(calculation_date: date) -> tuple[int, int]:
    """
    Deprecated helper kept for calendar-month API calls.

    Prefer ``payroll_period_for_calculation_date`` for calculation-date payroll runs.
    """
    period_start, _period_end = payroll_period_for_calculation_date(calculation_date)
    return period_start.year, period_start.month


def session_salary_deadline(session_date: date) -> datetime:
    """Reports must be approved within 48 hours of the session date."""
    naive = datetime.combine(session_date, time.min) + timedelta(hours=48)
    return timezone.make_aware(naive, timezone.get_current_timezone())


def is_salary_eligible(session_date: date, approved_at: datetime) -> bool:
    return approved_at <= session_salary_deadline(session_date)
