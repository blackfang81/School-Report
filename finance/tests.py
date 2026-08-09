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
from finance.models import TermBaseRate
from finance.services import calculate_teacher_salary
from reports.models import ReportStatus, SessionReport


class ReportFlowTest(APITestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username="teacher", password="pass12345", role=Role.TEACHER
        )
        self.officer = User.objects.create_user(
            username="officer", password="pass12345", role=Role.EDUCATION_OFFICER
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
        TermBaseRate.objects.create(term=self.term, base_rate=200_000)

    def auth(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_report_cycle(self):
        self.auth(self.teacher)
        response = self.client.post(
            reverse("report-list"),
            {
                "classroom": self.classroom.id,
                "session_date": "2026-01-15",
                "summary": "First session",
                "present_count": 10,
                "absent_count": 2,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["session_number"], 1)
        report_id = response.data["id"]

        self.auth(self.officer)
        response = self.client.post(
            reverse("report-approve", args=[report_id]),
            {"note": "Approved"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], ReportStatus.APPROVED)

        self.auth(self.teacher)
        response = self.client.patch(
            reverse("report-detail", args=[report_id]),
            {"summary": "Edit attempt"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

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


class SalaryCalculationTest(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username="teacher", password="pass12345", role=Role.TEACHER
        )
        school = School.objects.create(name="School")
        self.term = Term.objects.create(
            name="Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_summer=False,
        )
        classroom_90 = ClassRoom.objects.create(
            school=school,
            term=self.term,
            name="90",
            session_duration=90,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        classroom_60 = ClassRoom.objects.create(
            school=school,
            term=self.term,
            name="60",
            session_duration=60,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        classroom_120 = ClassRoom.objects.create(
            school=school,
            term=self.term,
            name="120",
            session_duration=120,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        TermBaseRate.objects.create(term=self.term, base_rate=200_000)
        session_date = date(2026, 1, 15)

        for i, classroom in enumerate([classroom_90] * 10 + [classroom_60] * 2 + [classroom_120]):
            SessionReport.objects.create(
                classroom=classroom,
                teacher=self.teacher,
                session_date=session_date,
                session_number=i + 1,
                summary="s",
                present_count=5,
                absent_count=1,
                status=ReportStatus.APPROVED,
                is_salary_eligible=True,
            )

        SessionReport.objects.create(
            classroom=classroom_90,
            teacher=self.teacher,
            session_date=session_date,
            session_number=14,
            summary="late",
            present_count=5,
            absent_count=1,
            status=ReportStatus.APPROVED,
            is_salary_eligible=False,
        )

    def test_salary_formula_example(self):
        amount = calculate_teacher_salary(self.teacher, 2026, 1)
        self.assertEqual(amount, 2_540_000)

    def test_no_salary_when_pending_report_exists(self):
        SessionReport.objects.create(
            classroom=ClassRoom.objects.first(),
            teacher=self.teacher,
            session_date=date(2026, 1, 20),
            session_number=99,
            summary="pending",
            present_count=5,
            absent_count=1,
            status=ReportStatus.PENDING,
        )
        amount = calculate_teacher_salary(self.teacher, 2026, 1)
        self.assertIsNone(amount)

    def test_no_salary_when_no_approved_reports(self):
        teacher2 = User.objects.create_user(
            username="t2", password="pass12345", role=Role.TEACHER
        )
        amount = calculate_teacher_salary(teacher2, 2026, 1)
        self.assertIsNone(amount)
