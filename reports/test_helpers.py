"""Shared helpers for report tests."""

from reports.models import ReportStatus, SessionReport


def create_report_for_session(class_session, teacher, **kwargs):
    """Create a report linked to a scheduled class session."""
    defaults = {
        "classroom": class_session.classroom,
        "class_session": class_session,
        "teacher": teacher,
        "session_date": class_session.session_date,
        "session_number": class_session.session_number,
        "summary": "Session summary",
        "present_count": 10,
        "absent_count": 2,
        "status": ReportStatus.PENDING,
    }
    defaults.update(kwargs)
    return SessionReport.objects.create(**defaults)


def approve_all_class_sessions(classroom, teacher):
    """Create approved eligible reports for every scheduled session in a class."""
    reports = []
    for session in classroom.sessions.filter(is_deleted=False).order_by("session_number"):
        reports.append(
            create_report_for_session(
                session,
                teacher,
                status=ReportStatus.APPROVED,
                is_salary_eligible=True,
            )
        )
    return reports
