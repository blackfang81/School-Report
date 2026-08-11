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
from reports.models import ReportStatus, SessionReport


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
        with patch("django.utils.timezone.now", return_value=on_time):
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
        with patch("django.utils.timezone.now", return_value=late_time):
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
        self.classroom = ClassRoom.objects.create(
            school=school,
            term=self.term,
            name="Class",
            session_duration=90,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        TeacherAssignment.objects.create(
            classroom=self.classroom,
            teacher=self.teacher,
            start_date=date(2026, 1, 1),
        )

    def auth(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _create_report(self, **kwargs):
        defaults = {
            "classroom": self.classroom.id,
            "session_date": "2026-01-15",
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

    def test_create_report_unassigned_class_fails(self):
        other_class = ClassRoom.objects.create(
            school=self.classroom.school,
            term=self.term,
            name="Other",
            session_duration=60,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.auth(self.teacher)
        response = self.client.post(
            reverse("report-list"),
            {
                "classroom": other_class.id,
                "session_date": "2026-01-15",
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
                "session_date": "2026-01-15",
                "summary": "s",
                "present_count": 5,
                "absent_count": 1,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_sees_only_own_reports(self):
        self._create_report()
        SessionReport.objects.create(
            classroom=self.classroom,
            teacher=self.teacher2,
            session_date=date(2026, 1, 20),
            session_number=2,
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
        self._create_report(session_date="2026-01-15")
        self.auth(self.teacher)
        self.client.post(
            reverse("report-list"),
            {
                "classroom": self.classroom.id,
                "session_date": "2026-02-15",
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
            {"note": "Good job"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], ReportStatus.APPROVED)
        self.assertEqual(response.data["officer_note"], "Good job")

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
