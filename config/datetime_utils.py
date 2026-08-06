import calendar
from datetime import date

def calendar_month_range(year: int, month: int) -> tuple[date, date]:
    """Return the first and last day of a Gregorian calendar month."""
    start = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end = date(year, month, last_day)
    return start, end



