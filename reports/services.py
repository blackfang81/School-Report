"""Business logic for teacher session report workflows."""

import calendar

from config.project_clock import project_localdate
from education.models import ClassSession, TeacherAssignment
from education.session_helpers import ensure_classroom_sessions
from reports.models import ReportStatus, SessionReport

WEEKDAY_NAMES = list(calendar.day_name)


def get_teacher_session_roster(teacher):
    """
    Return all class sessions assigned to ``teacher``, ordered by date.

    Each item includes report status and whether the teacher can submit or edit.
    """
    today = project_localdate()
    assignments = TeacherAssignment.objects.filter(
        teacher=teacher,
        is_deleted=False,
    ).select_related("classroom", "classroom__school", "classroom__term")

    roster = []
    seen_session_ids = set()

    for assignment in assignments:
        ensure_classroom_sessions(assignment.classroom)
        effective_end = assignment.get_effective_end_date()
        sessions = ClassSession.objects.filter(
            classroom=assignment.classroom,
            is_deleted=False,
            session_date__gte=assignment.start_date,
            session_date__lte=effective_end,
        ).select_related("classroom", "classroom__school", "classroom__term")

        for session in sessions:
            if session.id in seen_session_ids:
                continue
            seen_session_ids.add(session.id)

            report = (
                SessionReport.objects.filter(
                    class_session=session,
                    teacher=teacher,
                    is_deleted=False,
                )
                .select_related("classroom")
                .first()
            )

            if session.session_date > today:
                session_status = "upcoming"
                can_submit = False
                can_edit = False
            elif report is None:
                session_status = "ready"
                can_submit = True
                can_edit = False
            elif report.status == ReportStatus.PENDING:
                session_status = "pending"
                can_submit = False
                can_edit = True
            elif report.status == ReportStatus.REJECTED:
                session_status = "rejected"
                can_submit = False
                can_edit = True
            else:
                session_status = "approved"
                can_submit = False
                can_edit = False

            classroom = session.classroom
            roster.append(
                {
                    "class_session_id": session.id,
                    "classroom_id": classroom.id,
                    "classroom_name": classroom.name,
                    "school_name": classroom.school.name,
                    "term_name": classroom.term.name,
                    "session_number": session.session_number,
                    "session_date": session.session_date,
                    "weekday": WEEKDAY_NAMES[session.session_date.weekday()],
                    "session_duration": classroom.session_duration,
                    "session_status": session_status,
                    "can_submit": can_submit,
                    "can_edit": can_edit,
                    "report_id": report.id if report else None,
                    "report_status": report.status if report else None,
                    "is_salary_eligible": report.is_salary_eligible if report and report.status == ReportStatus.APPROVED else None,
                    "officer_note": report.officer_note if report else "",
                }
            )

    roster.sort(key=lambda item: (item["session_date"], item["session_number"]))
    return roster
