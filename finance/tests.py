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
from education.test_helpers import create_classroom_with_session_dates, january_2026_dates
from finance.models import SalaryRecord, TermBaseRate
from finance.services import calculate_monthly_salaries, calculate_teacher_salary
from reports.models import ReportStatus, SessionReport
from reports.test_helpers import approve_all_class_sessions, create_report_for_session


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
        classroom_90 = create_classroom_with_session_dates(
            school=school,
            term=self.term,
            teacher=self.teacher,
            name="90",
            session_duration=90,
            session_dates=january_2026_dates(11),
        )
        classroom_60 = create_classroom_with_session_dates(
            school=school,
            term=self.term,
            teacher=self.teacher,
            name="60",
            session_duration=60,
            session_dates=january_2026_dates(2, start_day=20),
        )
        classroom_120 = create_classroom_with_session_dates(
            school=school,
            term=self.term,
            teacher=self.teacher,
            name="120",
            session_duration=120,
            session_dates=[date(2026, 1, 25)],
        )
        TermBaseRate.objects.create(term=self.term, base_rate=200_000)

        for session in classroom_90.sessions.filter(session_number__lte=10):
            create_report_for_session(
                session,
                self.teacher,
                status=ReportStatus.APPROVED,
                is_salary_eligible=True,
            )

        late_session = classroom_90.sessions.get(session_number=11)
        create_report_for_session(
            late_session,
            self.teacher,
            status=ReportStatus.APPROVED,
            is_salary_eligible=False,
        )

        for session in classroom_60.sessions.all():
            create_report_for_session(
                session,
                self.teacher,
                status=ReportStatus.APPROVED,
                is_salary_eligible=True,
            )

        for session in classroom_120.sessions.all():
            create_report_for_session(
                session,
                self.teacher,
                status=ReportStatus.APPROVED,
                is_salary_eligible=True,
            )

        self.classroom_90 = classroom_90

    def test_salary_formula_example(self):
        amount = calculate_teacher_salary(self.teacher, 2026, 1)
        self.assertEqual(amount, 2_540_000)

    def test_no_salary_when_pending_report_exists(self):
        pending_session = create_classroom_with_session_dates(
            school=School.objects.first(),
            term=self.term,
            teacher=self.teacher,
            name="Pending Class",
            session_dates=[date(2026, 1, 28)],
        ).sessions.first()
        create_report_for_session(
            pending_session,
            self.teacher,
            status=ReportStatus.PENDING,
        )
        amount = calculate_teacher_salary(self.teacher, 2026, 1)
        self.assertIsNone(amount)

    def test_no_salary_when_class_sessions_incomplete(self):
        SessionReport.objects.filter(classroom=self.classroom_90).first().delete()
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
        classroom = create_classroom_with_session_dates(
            school=School.objects.first(),
            term=summer_term,
            teacher=self.teacher,
            name="Summer Class",
            session_duration=90,
            session_dates=[date(2027, 7, 15)],
        )
        TermBaseRate.objects.create(term=summer_term, base_rate=100_000)
        approve_all_class_sessions(classroom, self.teacher)
        amount = calculate_teacher_salary(self.teacher, 2027, 7)
        self.assertEqual(amount, Decimal(110_000))

    def test_no_salary_when_base_rate_missing(self):
        term_no_rate = Term.objects.create(
            name="No Rate",
            start_date=date(2027, 1, 1),
            end_date=date(2027, 6, 30),
        )
        classroom = create_classroom_with_session_dates(
            school=School.objects.first(),
            term=term_no_rate,
            teacher=self.teacher,
            name="No Rate Class",
            session_duration=90,
            session_dates=[date(2027, 1, 15)],
        )
        approve_all_class_sessions(classroom, self.teacher)
        amount = calculate_teacher_salary(self.teacher, 2027, 1)
        self.assertIsNone(amount)

    def test_soft_deleted_reports_excluded_from_salary(self):
        report = SessionReport.objects.filter(
            classroom=self.classroom_90, session_number=1
        ).first()
        report.delete()
        amount = calculate_teacher_salary(self.teacher, 2026, 1)
        self.assertIsNone(amount)

    def test_calculate_monthly_salaries_creates_records(self):
        records, skipped = calculate_monthly_salaries(2026, 1)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].amount, Decimal(2_540_000))
        self.assertTrue(SalaryRecord.objects.filter(teacher=self.teacher, year=2026, month=1).exists())

    def test_calculate_monthly_salaries_removes_stale_record(self):
        calculate_monthly_salaries(2026, 1)
        SessionReport.objects.filter(teacher=self.teacher).update(status=ReportStatus.PENDING)
        calculate_monthly_salaries(2026, 1)
        self.assertFalse(SalaryRecord.objects.filter(teacher=self.teacher, year=2026, month=1).exists())

    def test_future_month_sessions_do_not_block_current_month(self):
        """February sessions must not block January payroll when January is complete."""
        february_class = create_classroom_with_session_dates(
            school=School.objects.first(),
            term=self.term,
            teacher=self.teacher,
            name="Feb Only",
            session_duration=90,
            session_dates=[date(2026, 2, 10), date(2026, 2, 20)],
        )
        self.assertFalse(
            SessionReport.objects.filter(classroom=february_class).exists()
        )
        amount = calculate_teacher_salary(self.teacher, 2026, 1)
        self.assertEqual(amount, Decimal(2_540_000))

    def test_no_salary_when_all_approved_but_none_eligible(self):
        SessionReport.objects.filter(teacher=self.teacher).update(is_salary_eligible=False)
        amount = calculate_teacher_salary(self.teacher, 2026, 1)
        self.assertIsNone(amount)


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
        classroom = create_classroom_with_session_dates(
            school=school,
            term=self.term,
            teacher=self.teacher,
            name="Class",
            session_dates=[date(2026, 1, 15)],
        )
        TermBaseRate.objects.create(term=self.term, base_rate=200_000)
        approve_all_class_sessions(classroom, self.teacher)
        self.auth(self.finance)
        response = self.client.post(
            reverse("calculate_salaries"),
            {"year": 2026, "month": 1},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("records", response.data)
        self.assertEqual(len(response.data["records"]), 1)

    def test_calculate_salaries_with_calculation_date(self):
        school = School.objects.create(name="School")
        classroom = create_classroom_with_session_dates(
            school=school,
            term=self.term,
            teacher=self.teacher,
            name="Class",
            session_dates=[date(2025, 12, 20)],
        )
        TermBaseRate.objects.create(term=self.term, base_rate=200_000)
        approve_all_class_sessions(classroom, self.teacher)
        self.auth(self.finance)
        response = self.client.post(
            reverse("calculate_salaries"),
            {"calculation_date": "2026-01-15"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["period_start"], date(2025, 12, 16))
        self.assertEqual(response.data["period_end"], date(2026, 1, 14))
        self.assertEqual(len(response.data["records"]), 1)

    def test_calculate_salaries_uses_30_day_period(self):
        school = School.objects.create(name="School")
        classroom = create_classroom_with_session_dates(
            school=school,
            term=self.term,
            teacher=self.teacher,
            name="September Class",
            session_dates=[
                date(2026, 9, 1),
                date(2026, 9, 8),
                date(2026, 9, 15),
                date(2026, 9, 22),
            ],
        )
        TermBaseRate.objects.create(term=self.term, base_rate=200_000)
        approve_all_class_sessions(classroom, self.teacher)
        self.auth(self.finance)
        response = self.client.post(
            reverse("calculate_salaries"),
            {"calculation_date": "2026-09-15"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["period_start"], date(2026, 8, 16))
        self.assertEqual(response.data["period_end"], date(2026, 9, 14))
        self.assertEqual(len(response.data["records"]), 1)
        self.assertEqual(response.data["records"][0]["calculation_date"], "2026-09-15")

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
