from decimal import Decimal
import math

from accounts.models import Role, User
from config.datetime_utils import calendar_month_range
from finance.models import SalaryRecord, TermBaseRate
from reports.models import ReportStatus, SessionReport


def calculate_teacher_salary(teacher, year: int, month: int):
    """
    Calculate a teacher's salary for a Gregorian calendar month.

    Returns ``None`` when the teacher has no approved eligible reports,
    has pending/rejected reports in the month, or lacks a base rate for a term.
    """
    start, end = calendar_month_range(year, month)
    reports = SessionReport.objects.filter(
        teacher=teacher,
        session_date__gte=start,
        session_date__lte=end,
    ).select_related("classroom__term")

    if not reports.exists():
        return None

    if reports.exclude(status=ReportStatus.APPROVED).exists():
        return None

    eligible = reports.filter(is_salary_eligible=True)
    if not eligible.exists():
        return None

    total = Decimal("0")
    terms = {r.classroom.term for r in eligible}
    for term in terms:
        term_reports = [r for r in eligible if r.classroom.term_id == term.id]
        duration_counts = {60: 0, 90: 0, 120: 0}
        for report in term_reports:
            duration_counts[report.classroom.session_duration] += 1

        try:
            x = Decimal(term.base_rate.base_rate)
        except TermBaseRate.DoesNotExist:
            continue

        a = duration_counts[90]
        b = duration_counts[60]
        c = duration_counts[120]
        wage = Decimal(a) * x + Decimal(b) * (x * Decimal("0.7")) + Decimal(c) * (x * Decimal("1.3"))
        if term.is_summer:
            wage *= Decimal("1.1")
        total += wage

    if total <= 0:
        return None

    return Decimal(math.ceil(float(total)))


def calculate_monthly_salaries(year: int, month: int):
    """
    Calculate and persist salary records for all active teachers in a month.

    Removes stale records when a teacher no longer qualifies.
    Returns the list of created/updated ``SalaryRecord`` instances.
    """
    teachers = User.objects.filter(role=Role.TEACHER, is_active=True)
    created = []
    for teacher in teachers:
        amount = calculate_teacher_salary(teacher, year, month)
        if amount is None:
            SalaryRecord.objects.filter(
                teacher=teacher,
                year=year,
                month=month,
            ).delete()
            continue
        record, _ = SalaryRecord.objects.update_or_create(
            teacher=teacher,
            year=year,
            month=month,
            defaults={"amount": amount},
        )
        created.append(record)
    return created
