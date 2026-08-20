from datetime import date
from decimal import Decimal
import math

from accounts.models import Role, User
from config.datetime_utils import calendar_month_range
from education.models import ClassSession, TeacherAssignment
from finance.models import SalaryRecord, TermBaseRate
from reports.models import ReportStatus, SessionReport


SKIP_REASONS = {
    "no_sessions": "No scheduled sessions in this payroll period.",
    "incomplete_reports": "Not all sessions in this period are approved.",
    "no_eligible_sessions": "All sessions are approved, but none qualify for 48-hour salary.",
    "missing_base_rate": "Term base rate is not configured.",
    "zero_amount": "Calculated salary amount is zero.",
}


def get_teacher_sessions_in_period(
    teacher,
    period_start: date,
    period_end: date,
) -> list[ClassSession]:
    """Return scheduled sessions in ``period_start``..``period_end`` for ``teacher`` assignments."""
    assignments = TeacherAssignment.objects.filter(
        teacher=teacher,
        is_deleted=False,
    ).select_related("classroom")

    sessions = []
    seen_ids = set()
    for assignment in assignments:
        effective_end = assignment.get_effective_end_date()
        range_start = max(period_start, assignment.start_date)
        range_end = min(period_end, effective_end)
        if range_start > range_end:
            continue

        for session in ClassSession.objects.filter(
            classroom=assignment.classroom,
            is_deleted=False,
            session_date__gte=range_start,
            session_date__lte=range_end,
        ).select_related("classroom", "classroom__term"):
            if session.id not in seen_ids:
                seen_ids.add(session.id)
                sessions.append(session)

    sessions.sort(key=lambda item: (item.session_date, item.session_number))
    return sessions


def get_teacher_sessions_in_month(teacher, year: int, month: int) -> list[ClassSession]:
    """Return scheduled sessions in a Gregorian calendar month."""
    start, end = calendar_month_range(year, month)
    return get_teacher_sessions_in_period(teacher, start, end)


def month_sessions_fully_approved(teacher, sessions: list[ClassSession]) -> bool:
    """Return True when every session has an approved report from ``teacher``."""
    if not sessions:
        return False

    reports = {
        report.class_session_id: report
        for report in SessionReport.objects.filter(
            teacher=teacher,
            class_session_id__in=[session.id for session in sessions],
            is_deleted=False,
        )
    }

    for session in sessions:
        report = reports.get(session.id)
        if report is None or report.status != ReportStatus.APPROVED:
            return False
    return True


def _period_report_stats(teacher, period_sessions: list[ClassSession]) -> dict:
    reports = {
        report.class_session_id: report
        for report in SessionReport.objects.filter(
            teacher=teacher,
            class_session_id__in=[session.id for session in period_sessions],
            is_deleted=False,
        ).select_related("classroom", "classroom__term")
    }
    approved = 0
    eligible = 0
    for session in period_sessions:
        report = reports.get(session.id)
        if report and report.status == ReportStatus.APPROVED:
            approved += 1
            if report.is_salary_eligible:
                eligible += 1
    return {
        "reports": reports,
        "approved_count": approved,
        "eligible_count": eligible,
    }


def explain_teacher_salary_for_period(teacher, period_start: date, period_end: date) -> dict:
    """Return salary amount plus a skip reason when the teacher does not qualify."""
    period_sessions = get_teacher_sessions_in_period(teacher, period_start, period_end)
    session_count = len(period_sessions)
    if not period_sessions:
        return {
            "amount": None,
            "reason_code": "no_sessions",
            "reason": SKIP_REASONS["no_sessions"],
            "session_count": 0,
            "approved_count": 0,
            "eligible_count": 0,
        }

    stats = _period_report_stats(teacher, period_sessions)
    if stats["approved_count"] != session_count:
        return {
            "amount": None,
            "reason_code": "incomplete_reports",
            "reason": SKIP_REASONS["incomplete_reports"],
            "session_count": session_count,
            "approved_count": stats["approved_count"],
            "eligible_count": stats["eligible_count"],
        }

    if stats["eligible_count"] == 0:
        return {
            "amount": None,
            "reason_code": "no_eligible_sessions",
            "reason": SKIP_REASONS["no_eligible_sessions"],
            "session_count": session_count,
            "approved_count": stats["approved_count"],
            "eligible_count": 0,
        }

    reports = stats["reports"]
    eligible_reports = [
        reports[session.id]
        for session in period_sessions
        if reports[session.id].is_salary_eligible
    ]

    total = Decimal("0")
    terms = {report.classroom.term for report in eligible_reports}
    for term in terms:
        term_reports = [report for report in eligible_reports if report.classroom.term_id == term.id]
        duration_counts = {60: 0, 90: 0, 120: 0}
        for report in term_reports:
            duration_counts[report.classroom.session_duration] += 1

        try:
            x = Decimal(term.base_rate.base_rate)
        except TermBaseRate.DoesNotExist:
            return {
                "amount": None,
                "reason_code": "missing_base_rate",
                "reason": SKIP_REASONS["missing_base_rate"],
                "session_count": session_count,
                "approved_count": stats["approved_count"],
                "eligible_count": stats["eligible_count"],
            }

        a = duration_counts[90]
        b = duration_counts[60]
        c = duration_counts[120]
        wage = Decimal(a) * x + Decimal(b) * (x * Decimal("0.7")) + Decimal(c) * (x * Decimal("1.3"))
        if term.is_summer:
            wage *= Decimal("1.1")
        total += wage

    if total <= 0:
        return {
            "amount": None,
            "reason_code": "zero_amount",
            "reason": SKIP_REASONS["zero_amount"],
            "session_count": session_count,
            "approved_count": stats["approved_count"],
            "eligible_count": stats["eligible_count"],
        }

    return {
        "amount": Decimal(math.ceil(float(total))),
        "reason_code": None,
        "reason": None,
        "session_count": session_count,
        "approved_count": stats["approved_count"],
        "eligible_count": stats["eligible_count"],
    }


def explain_teacher_salary(teacher, year: int, month: int) -> dict:
    start, end = calendar_month_range(year, month)
    return explain_teacher_salary_for_period(teacher, start, end)


def calculate_teacher_salary(teacher, year: int, month: int):
    """
    Calculate a teacher's salary for a Gregorian calendar month.

    Rules:
    - Consider only sessions scheduled in ``year``/``month`` for the teacher's assignments.
    - Every such session must have an approved report (including late/non-eligible ones).
    - Only ``is_salary_eligible`` sessions (approved within 48 hours) are paid.
    - Returns ``None`` when there are no sessions, any session is incomplete, no eligible
      sessions, or a term base rate is missing.
    """
    return explain_teacher_salary(teacher, year, month)["amount"]


def _should_report_skip(outcome: dict, teacher) -> bool:
    return outcome["session_count"] > 0 or SessionReport.objects.filter(
        teacher=teacher, is_deleted=False
    ).exists()


def _build_skip_entry(teacher, outcome: dict) -> dict:
    return {
        "teacher_id": teacher.id,
        "teacher_name": teacher.get_full_name() or teacher.username,
        "reason_code": outcome["reason_code"],
        "reason": outcome["reason"],
        "session_count": outcome["session_count"],
        "approved_count": outcome["approved_count"],
        "eligible_count": outcome["eligible_count"],
    }


def calculate_salaries_for_period(
    period_start: date,
    period_end: date,
    *,
    calculation_date: date | None = None,
    record_year: int | None = None,
    record_month: int | None = None,
):
    """
    Calculate and persist salary records for all active teachers in a date range.

    When ``calculation_date`` is provided, records are keyed by that date.
    Otherwise records use ``record_year``/``record_month`` (calendar-month mode).
    """
    teachers = User.objects.filter(role=Role.TEACHER, is_active=True)
    created = []
    skipped = []
    for teacher in teachers:
        outcome = explain_teacher_salary_for_period(teacher, period_start, period_end)
        amount = outcome["amount"]
        if amount is None:
            if calculation_date is not None:
                SalaryRecord.objects.filter(
                    teacher=teacher,
                    calculation_date=calculation_date,
                ).delete()
            elif record_year is not None and record_month is not None:
                SalaryRecord.objects.filter(
                    teacher=teacher,
                    year=record_year,
                    month=record_month,
                    calculation_date__isnull=True,
                ).delete()
            if _should_report_skip(outcome, teacher):
                skipped.append(_build_skip_entry(teacher, outcome))
            continue

        if calculation_date is not None:
            record, _ = SalaryRecord.objects.update_or_create(
                teacher=teacher,
                calculation_date=calculation_date,
                defaults={
                    "amount": amount,
                    "period_start": period_start,
                    "period_end": period_end,
                    "year": period_end.year,
                    "month": period_end.month,
                },
            )
        else:
            record, _ = SalaryRecord.objects.update_or_create(
                teacher=teacher,
                year=record_year,
                month=record_month,
                calculation_date=None,
                defaults={
                    "amount": amount,
                    "period_start": period_start,
                    "period_end": period_end,
                },
            )
        created.append(record)
    return created, skipped


def calculate_monthly_salaries(year: int, month: int):
    """Calculate salaries for a full calendar month."""
    start, end = calendar_month_range(year, month)
    return calculate_salaries_for_period(
        start,
        end,
        record_year=year,
        record_month=month,
    )
