"""Comprehensive tests for the reports app: models, API, soft delete, and workflow."""

from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, User
from education.models import ClassRoom, School, TeacherAssignment, Term
from education.test_helpers import create_classroom_with_session_dates
from reports.models import ReportStatus, SessionReport
from reports.test_helpers import create_report_for_session


class SessionReportModelTest(TestCase):
    """Unit tests for SessionReport model methods and constraints."""

    def setUp(self):
        self.teacher = User.objects.create_user(
            username="t1", password="pass12345", role=Role.TEACHER
        )
        school = School.objects.create(name="School")
        self.term = Term.objects.create(
            name="Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.classroom = ClassRoom.objects.create(
            school=school,
            term=self.term,
            name="Class A",
            session_duration=90,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        TeacherAssignment.objects.create(
            classroom=self.classroom,
            teacher=self.teacher,
            start_date=date(2026, 1, 1),
        )

    def test_next_session_number_starts_at_one(self):
        self.assertEqual(SessionReport.next_session_number(self.classroom), 1)

    def test_next_session_number_increments(self):
        SessionReport.objects.create(
            classroom=self.classroom,
            teacher=self.teacher,
            session_date=date(2026, 1, 10),
            session_number=1,
            summary="s",
            present_count=5,
            absent_count=1,
        )
        self.assertEqual(SessionReport.next_session_number(self.classroom), 2)

    def test_next_session_number_ignores_soft_deleted(self):
        report = SessionReport.objects.create(
            classroom=self.classroom,
            teacher=self.teacher,
            session_date=date(2026, 1, 10),
            session_number=1,
            summary="s",
            present_count=5,
            absent_count=1,
        )
        report.delete()
        self.assertEqual(SessionReport.next_session_number(self.classroom), 1)

    def test_teacher_owns_class_on_date_true(self):
        self.assertTrue(
            SessionReport.teacher_owns_class_on_date(
                self.teacher, self.classroom, date(2026, 6, 1)
            )
        )

    def test_teacher_owns_class_on_date_false_before_assignment(self):
        self.assertFalse(
            SessionReport.teacher_owns_class_on_date(
                self.teacher, self.classroom, date(2025, 12, 31)
            )
        )

    def test_teacher_owns_class_on_date_false_after_end(self):
        assignment = TeacherAssignment.objects.get(classroom=self.classroom)
        assignment.end_date = date(2026, 3, 31)
        assignment.save()
        self.assertFalse(
            SessionReport.teacher_owns_class_on_date(
                self.teacher, self.classroom, date(2026, 6, 1)
            )
        )

    def test_mark_approved_sets_status_and_eligibility(self):
        session_date = date(2026, 1, 15)
        report = SessionReport.objects.create(
            classroom=self.classroom,
            teacher=self.teacher,
            session_date=session_date,
            session_number=1,
            summary="s",
            present_count=5,
            absent_count=1,
        )
        on_time = timezone.make_aware(
            timezone.datetime.combine(session_date, timezone.datetime.min.time())
            + timedelta(hours=24)
        )
        with patch("reports.models.project_now", return_value=on_time):
            report.mark_approved()
        report.refresh_from_db()
        self.assertEqual(report.status, ReportStatus.APPROVED)
        self.assertIsNotNone(report.approved_at)
        self.assertTrue(report.is_salary_eligible)

    def test_mark_rejected_clears_eligibility(self):
        report = SessionReport.objects.create(
            classroom=self.classroom,
            teacher=self.teacher,
            session_date=date(2026, 1, 15),
            session_number=1,
            summary="s",
            present_count=5,
            absent_count=1,
            status=ReportStatus.APPROVED,
            is_salary_eligible=True,
        )
        report.mark_rejected("Needs revision")
        report.refresh_from_db()
        self.assertEqual(report.status, ReportStatus.REJECTED)
        self.assertEqual(report.officer_note, "Needs revision")
        self.assertFalse(report.is_salary_eligible)
        self.assertIsNone(report.approved_at)

    def test_soft_delete_hides_from_default_manager(self):
        report = SessionReport.objects.create(
            classroom=self.classroom,
            teacher=self.teacher,
            session_date=date(2026, 1, 15),
            session_number=1,
            summary="s",
            present_count=5,
            absent_count=1,
        )
        report.delete()
        self.assertEqual(SessionReport.objects.count(), 0)
        self.assertTrue(SessionReport.all_objects.filter(is_deleted=True).exists())

    def test_restore_soft_deleted_report(self):
        report = SessionReport.objects.create(
            classroom=self.classroom,
            teacher=self.teacher,
            session_date=date(2026, 1, 15),
            session_number=1,
            summary="s",
            present_count=5,
            absent_count=1,
        )
        report.delete()
        report.restore()
        self.assertFalse(report.is_deleted)
        self.assertEqual(SessionReport.objects.count(), 1)

    def test_late_approval_not_salary_eligible(self):
        session_date = date(2026, 1, 1)
        report = SessionReport.objects.create(
            classroom=self.classroom,
            teacher=self.teacher,
            session_date=session_date,
            session_number=1,
            summary="test",
            present_count=5,
            absent_count=1,
        )
        late_time = timezone.make_aware(
            timezone.datetime.combine(session_date, timezone.datetime.min.time())
            + timedelta(hours=49)
        )
        with patch("reports.models.project_now", return_value=late_time):
            report.mark_approved()
        self.assertFalse(report.is_salary_eligible)


class SessionReportAPITest(APITestCase):
    """API integration tests for report endpoints."""

    def setUp(self):
        self.teacher = User.objects.create_user(
            username="teacher", password="pass12345", role=Role.TEACHER
        )
        self.teacher2 = User.objects.create_user(
            username="teacher2", password="pass12345", role=Role.TEACHER
        )
        self.officer = User.objects.create_user(
            username="officer", password="pass12345", role=Role.EDUCATION_OFFICER
        )
        self.finance = User.objects.create_user(
            username="finance", password="pass12345", role=Role.FINANCE_OFFICER
        )
        school = School.objects.create(name="School")
        self.term = Term.objects.create(
            name="Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.classroom = create_classroom_with_session_dates(
            school=school,
            term=self.term,
            teacher=self.teacher,
            session_dates=[date(2026, 1, 15), date(2026, 2, 15)],
            name="Class",
        )
        self.session = self.classroom.sessions.order_by("session_number").first()
        self.second_session = self.classroom.sessions.order_by("session_number").last()

    def auth(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _create_report(self, **kwargs):
        session = kwargs.pop("class_session", self.session)
        defaults = {
            "classroom": self.classroom.id,
            "class_session": session.id,
            "summary": "Session summary",
            "present_count": 10,
            "absent_count": 2,
        }
        defaults.update(kwargs)
        self.auth(self.teacher)
        return self.client.post(reverse("report-list"), defaults, format="json")

    def test_create_report_success(self):
        response = self._create_report()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["session_number"], 1)
        self.assertEqual(response.data["status"], ReportStatus.PENDING)
        self.assertEqual(response.data["teacher"], self.teacher.id)

    def test_my_sessions_lists_assigned_sessions(self):
        self.auth(self.teacher)
        response = self.client.get(reverse("report-my-sessions"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["session_number"], 1)

    def test_my_sessions_marks_upcoming_sessions(self):
        self.auth(self.teacher)
        with patch("reports.services.project_localdate", return_value=date(2026, 1, 20)):
            response = self.client.get(reverse("report-my-sessions"))
        by_number = {item["session_number"]: item for item in response.data}
        self.assertEqual(by_number[1]["session_status"], "ready")
        self.assertTrue(by_number[1]["can_submit"])
        self.assertEqual(by_number[2]["session_status"], "upcoming")
        self.assertFalse(by_number[2]["can_submit"])

    def test_my_sessions_includes_salary_eligibility_when_approved(self):
        create_response = self._create_report()
        report_id = create_response.data["id"]
        self.auth(self.officer)
        with patch("reports.models.project_now", return_value=timezone.make_aware(
            timezone.datetime.combine(date(2026, 1, 16), timezone.datetime.min.time())
        )):
            approve_response = self.client.post(
                reverse("report-approve", args=[report_id]),
                {"note": ""},
                format="json",
            )
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        self.auth(self.teacher)
        with patch("reports.services.project_localdate", return_value=date(2026, 1, 20)):
            response = self.client.get(reverse("report-my-sessions"))
        session_one = next(item for item in response.data if item["session_number"] == 1)
        self.assertEqual(session_one["report_status"], ReportStatus.APPROVED)
        self.assertTrue(session_one["is_salary_eligible"])
        session_two = next(item for item in response.data if item["session_number"] == 2)
        self.assertIsNone(session_two["is_salary_eligible"])

    def test_create_report_for_future_session_fails(self):
        with patch("reports.serializers.project_localdate", return_value=date(2026, 1, 10)):
            response = self._create_report(class_session=self.session)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_report_unassigned_class_fails(self):
        other_class = create_classroom_with_session_dates(
            school=self.classroom.school,
            term=self.term,
            session_dates=[date(2026, 1, 20)],
            name="Other",
            session_duration=60,
        )
        other_session = other_class.sessions.first()
        self.auth(self.teacher)
        response = self.client.post(
            reverse("report-list"),
            {
                "classroom": other_class.id,
                "class_session": other_session.id,
                "summary": "s",
                "present_count": 5,
                "absent_count": 1,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_report_zero_attendance_fails(self):
        response = self._create_report(present_count=0, absent_count=0)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_officer_cannot_create_report(self):
        self.auth(self.officer)
        response = self.client.post(
            reverse("report-list"),
            {
                "classroom": self.classroom.id,
                "class_session": self.session.id,
                "summary": "s",
                "present_count": 5,
                "absent_count": 1,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_sees_only_own_reports(self):
        self._create_report()
        second = self.classroom.sessions.order_by("session_number")[1]
        create_report_for_session(
            second,
            self.teacher2,
            summary="other",
            present_count=5,
            absent_count=1,
        )
        TeacherAssignment.objects.create(
            classroom=self.classroom,
            teacher=self.teacher2,
            start_date=date(2026, 1, 1),
        )
        self.auth(self.teacher)
        response = self.client.get(reverse("report-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_finance_officer_sees_no_reports(self):
        self._create_report()
        self.auth(self.finance)
        response = self.client.get(reverse("report-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 0)

    def test_officer_filters_by_school(self):
        self._create_report()
        self.auth(self.officer)
        response = self.client.get(
            reverse("report-list"),
            {"school": self.classroom.school_id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_officer_filters_by_date_range(self):
        self._create_report()
        self.auth(self.teacher)
        self.client.post(
            reverse("report-list"),
            {
                "classroom": self.classroom.id,
                "class_session": self.second_session.id,
                "summary": "second",
                "present_count": 8,
                "absent_count": 1,
            },
            format="json",
        )
        self.auth(self.officer)
        response = self.client.get(
            reverse("report-list"),
            {"date_from": "2026-02-01", "date_to": "2026-02-28"},
        )
        self.assertEqual(len(response.data["results"]), 1)

    def test_approve_report(self):
        create_resp = self._create_report()
        report_id = create_resp.data["id"]
        self.auth(self.officer)
        response = self.client.post(
            reverse("report-approve", args=[report_id]),
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], ReportStatus.APPROVED)
        self.assertEqual(response.data["officer_note"], "")

    def test_reject_report(self):
        create_resp = self._create_report()
        report_id = create_resp.data["id"]
        self.auth(self.officer)
        response = self.client.post(
            reverse("report-reject", args=[report_id]),
            {"note": "Incomplete"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], ReportStatus.REJECTED)

    def test_reject_report_requires_reason(self):
        create_resp = self._create_report()
        report_id = create_resp.data["id"]
        self.auth(self.officer)
        response = self.client.post(reverse("report-reject", args=[report_id]), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_late_approval_via_api_not_salary_eligible(self):
        create_resp = self._create_report()
        report_id = create_resp.data["id"]
        self.auth(self.officer)
        session_date = date(2026, 1, 15)
        late_time = timezone.make_aware(
            timezone.datetime.combine(session_date, timezone.datetime.min.time())
            + timedelta(hours=49)
        )
        with patch("reports.models.project_now", return_value=late_time):
            response = self.client.post(reverse("report-approve", args=[report_id]), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_salary_eligible"])

    def test_officer_filters_by_term(self):
        self._create_report()
        self.auth(self.officer)
        response = self.client.get(reverse("report-list"), {"term": self.term.id})
        self.assertEqual(len(response.data["results"]), 1)

    def test_teacher_cannot_approve(self):
        create_resp = self._create_report()
        self.auth(self.teacher)
        response = self.client.post(
            reverse("report-approve", args=[create_resp.data["id"]]),
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_edit_pending_report_resets_status(self):
        create_resp = self._create_report()
        report_id = create_resp.data["id"]
        self.auth(self.officer)
        self.client.post(reverse("report-approve", args=[report_id]), {}, format="json")
        self.auth(self.teacher)
        response = self.client.patch(
            reverse("report-detail", args=[report_id]),
            {"summary": "Edit attempt"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_edit_rejected_report_resets_to_pending(self):
        create_resp = self._create_report()
        report_id = create_resp.data["id"]
        self.auth(self.officer)
        self.client.post(
            reverse("report-reject", args=[report_id]),
            {"note": "fix it"},
            format="json",
        )
        self.auth(self.teacher)
        response = self.client.patch(
            reverse("report-detail", args=[report_id]),
            {"summary": "Fixed summary"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], ReportStatus.PENDING)
        self.assertEqual(response.data["officer_note"], "")

    def test_teacher_soft_delete_own_pending_report(self):
        create_resp = self._create_report()
        report_id = create_resp.data["id"]
        self.auth(self.teacher)
        response = self.client.delete(reverse("report-detail", args=[report_id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(SessionReport.objects.filter(id=report_id).exists())
        self.assertTrue(SessionReport.all_objects.filter(id=report_id, is_deleted=True).exists())

    def test_teacher_cannot_delete_approved_report(self):
        create_resp = self._create_report()
        report_id = create_resp.data["id"]
        self.auth(self.officer)
        self.client.post(reverse("report-approve", args=[report_id]), {}, format="json")
        self.auth(self.teacher)
        response = self.client.delete(reverse("report-detail", args=[report_id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_officer_can_soft_delete_any_report(self):
        create_resp = self._create_report()
        report_id = create_resp.data["id"]
        self.auth(self.officer)
        self.client.post(reverse("report-approve", args=[report_id]), {}, format="json")
        response = self.client.delete(reverse("report-detail", args=[report_id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_session_number_reuse_after_soft_delete(self):
        create_resp = self._create_report()
        report_id = create_resp.data["id"]
        self.auth(self.teacher)
        self.client.delete(reverse("report-detail", args=[report_id]))
        response = self._create_report()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["session_number"], 1)

    def test_report_detail_includes_school_name(self):
        create_resp = self._create_report()
        self.auth(self.teacher)
        response = self.client.get(reverse("report-detail", args=[create_resp.data["id"]]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["school_name"], "School")

    def test_unauthenticated_access_denied(self):
        response = self.client.get(reverse("report-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
