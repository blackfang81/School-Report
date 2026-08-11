"""Comprehensive tests for finance app: salary calculation, API, and soft delete."""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, User
from education.models import ClassRoom, School, TeacherAssignment, Term
from finance.models import SalaryRecord, TermBaseRate
from finance.services import calculate_monthly_salaries, calculate_teacher_salary
from reports.models import ReportStatus, SessionReport


class SalaryCalculationTest(TestCase):
    """Unit tests for salary calculation service functions."""

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

    def test_summer_term_bonus(self):
        summer_term = Term.objects.create(
            name="Summer",
            start_date=date(2027, 7, 1),
            end_date=date(2027, 8, 31),
            is_summer=True,
        )
        classroom = ClassRoom.objects.create(
            school=School.objects.first(),
            term=summer_term,
            name="Summer Class",
            session_duration=90,
            start_date=date(2027, 7, 1),
            end_date=date(2027, 8, 31),
        )
        TermBaseRate.objects.create(term=summer_term, base_rate=100_000)
        SessionReport.objects.create(
            classroom=classroom,
            teacher=self.teacher,
            session_date=date(2027, 7, 15),
            session_number=1,
            summary="s",
            present_count=5,
            absent_count=1,
            status=ReportStatus.APPROVED,
            is_salary_eligible=True,
        )
        amount = calculate_teacher_salary(self.teacher, 2027, 7)
        self.assertEqual(amount, Decimal(110_000))

    def test_no_salary_when_base_rate_missing(self):
        term_no_rate = Term.objects.create(
            name="No Rate",
            start_date=date(2027, 1, 1),
            end_date=date(2027, 6, 30),
        )
        classroom = ClassRoom.objects.create(
            school=School.objects.first(),
            term=term_no_rate,
            name="No Rate Class",
            session_duration=90,
            start_date=date(2027, 1, 1),
            end_date=date(2027, 6, 30),
        )
        SessionReport.objects.create(
            classroom=classroom,
            teacher=self.teacher,
            session_date=date(2027, 1, 15),
            session_number=1,
            summary="s",
            present_count=5,
            absent_count=1,
            status=ReportStatus.APPROVED,
            is_salary_eligible=True,
        )
        amount = calculate_teacher_salary(self.teacher, 2027, 1)
        self.assertIsNone(amount)

    def test_soft_deleted_reports_excluded_from_salary(self):
        report = SessionReport.objects.filter(session_number=1).first()
        report.delete()
        amount = calculate_teacher_salary(self.teacher, 2026, 1)
        self.assertIsNotNone(amount)
        self.assertLess(amount, Decimal(2_540_000))

    def test_calculate_monthly_salaries_creates_records(self):
        records = calculate_monthly_salaries(2026, 1)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].amount, Decimal(2_540_000))
        self.assertTrue(SalaryRecord.objects.filter(teacher=self.teacher, year=2026, month=1).exists())

    def test_calculate_monthly_salaries_removes_stale_record(self):
        calculate_monthly_salaries(2026, 1)
        SessionReport.objects.filter(teacher=self.teacher).update(status=ReportStatus.PENDING)
        calculate_monthly_salaries(2026, 1)
        self.assertFalse(SalaryRecord.objects.filter(teacher=self.teacher, year=2026, month=1).exists())


class TermBaseRateModelTest(TestCase):
    """Tests for TermBaseRate soft delete."""

    def setUp(self):
        self.term = Term.objects.create(
            name="Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )

    def test_soft_delete_hides_rate(self):
        rate = TermBaseRate.objects.create(term=self.term, base_rate=100_000)
        rate.delete()
        self.assertEqual(TermBaseRate.objects.count(), 0)
        self.assertTrue(TermBaseRate.all_objects.filter(is_deleted=True).exists())

    def test_restore_rate(self):
        rate = TermBaseRate.objects.create(term=self.term, base_rate=100_000)
        rate.delete()
        rate.restore()
        self.assertEqual(TermBaseRate.objects.count(), 1)


class FinanceAPITest(APITestCase):
    """API integration tests for finance endpoints."""

    def setUp(self):
        self.finance = User.objects.create_user(
            username="finance", password="pass12345", role=Role.FINANCE_OFFICER
        )
        self.teacher = User.objects.create_user(
            username="teacher", password="pass12345", role=Role.TEACHER
        )
        self.officer = User.objects.create_user(
            username="officer", password="pass12345", role=Role.EDUCATION_OFFICER
        )
        self.term = Term.objects.create(
            name="Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )

    def auth(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_create_base_rate(self):
        self.auth(self.finance)
        response = self.client.post(
            reverse("base-rate-list"),
            {"term": self.term.id, "base_rate": "200000"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TermBaseRate.objects.count(), 1)

    def test_list_base_rates(self):
        TermBaseRate.objects.create(term=self.term, base_rate=200_000)
        self.auth(self.finance)
        response = self.client.get(reverse("base-rate-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_update_base_rate(self):
        rate = TermBaseRate.objects.create(term=self.term, base_rate=200_000)
        self.auth(self.finance)
        response = self.client.patch(
            reverse("base-rate-detail", args=[rate.id]),
            {"base_rate": "250000"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rate.refresh_from_db()
        self.assertEqual(rate.base_rate, Decimal(250000))

    def test_soft_delete_base_rate(self):
        rate = TermBaseRate.objects.create(term=self.term, base_rate=200_000)
        self.auth(self.finance)
        response = self.client.delete(reverse("base-rate-detail", args=[rate.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        rate.refresh_from_db()
        self.assertTrue(rate.is_deleted)

    def test_teacher_cannot_access_base_rates(self):
        self.auth(self.teacher)
        response = self.client.get(reverse("base-rate-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_officer_cannot_access_base_rates(self):
        self.auth(self.officer)
        response = self.client.get(reverse("base-rate-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_calculate_salaries_endpoint(self):
        school = School.objects.create(name="School")
        classroom = ClassRoom.objects.create(
            school=school,
            term=self.term,
            name="Class",
            session_duration=90,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        TeacherAssignment.objects.create(
            classroom=classroom,
            teacher=self.teacher,
            start_date=date(2026, 1, 1),
        )
        TermBaseRate.objects.create(term=self.term, base_rate=200_000)
        SessionReport.objects.create(
            classroom=classroom,
            teacher=self.teacher,
            session_date=date(2026, 1, 15),
            session_number=1,
            summary="s",
            present_count=10,
            absent_count=2,
            status=ReportStatus.APPROVED,
            is_salary_eligible=True,
        )
        self.auth(self.finance)
        response = self.client.post(
            reverse("calculate_salaries"),
            {"year": 2026, "month": 1},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("records", response.data)
        self.assertEqual(len(response.data["records"]), 1)

    def test_calculate_salaries_invalid_month(self):
        self.auth(self.finance)
        response = self.client.post(
            reverse("calculate_salaries"),
            {"year": 2026, "month": 13},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_teacher_my_salaries(self):
        SalaryRecord.objects.create(
            teacher=self.teacher,
            year=2026,
            month=1,
            amount=1_000_000,
        )
        SalaryRecord.objects.create(
            teacher=self.finance,
            year=2026,
            month=1,
            amount=2_000_000,
        )
        self.auth(self.teacher)
        response = self.client.get(reverse("salary-my-salaries"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["amount"], "1000000")

    def test_finance_lists_all_salaries(self):
        SalaryRecord.objects.create(
            teacher=self.teacher,
            year=2026,
            month=1,
            amount=1_000_000,
        )
        self.auth(self.finance)
        response = self.client.get(reverse("salary-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_filter_salaries_by_year(self):
        SalaryRecord.objects.create(
            teacher=self.teacher, year=2026, month=1, amount=1_000_000
        )
        SalaryRecord.objects.create(
            teacher=self.teacher, year=2025, month=12, amount=900_000
        )
        self.auth(self.finance)
        response = self.client.get(reverse("salary-list"), {"year": 2026})
        self.assertEqual(len(response.data["results"]), 1)

    def test_teacher_cannot_calculate_salaries(self):
        self.auth(self.teacher)
        response = self.client.post(
            reverse("calculate_salaries"),
            {"year": 2026, "month": 1},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
