"""Comprehensive tests for shared config utilities."""

from datetime import date, datetime, timezone as dt_timezone

from django.core.exceptions import ValidationError
from django.test import TestCase, RequestFactory
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.test import force_authenticate
from rest_framework.views import APIView

from config.datetime_utils import (
    calendar_month_range,
    is_salary_eligible,
    session_salary_deadline,
)
from config.exceptions import ValidationErrorWithCode, custom_exception_handler
from config.mixins import SoftDeleteModel
from education.models import ClassRoom, School, Term


class SoftDeleteMixinTest(TestCase):
    """Verify soft-delete behaviour on models using SoftDeleteModel."""

    def test_soft_delete_hides_from_default_manager(self):
        school = School.objects.create(name="Visible")
        school.delete()
        self.assertEqual(School.objects.count(), 0)
        self.assertEqual(School.all_objects.filter(is_deleted=True).count(), 1)

    def test_restore_soft_deleted_record(self):
        school = School.objects.create(name="Restore Me")
        school.delete()
        school.restore()
        self.assertFalse(school.is_deleted)
        self.assertIsNone(school.deleted_at)
        self.assertEqual(School.objects.count(), 1)

    def test_hard_delete_removes_record(self):
        school = School.objects.create(name="Hard Delete")
        pk = school.pk
        school.hard_delete()
        self.assertFalse(School.all_objects.filter(pk=pk).exists())

    def test_queryset_bulk_soft_delete(self):
        School.objects.create(name="A")
        School.objects.create(name="B")
        School.objects.all().delete()
        self.assertEqual(School.objects.count(), 0)
        self.assertEqual(School.all_objects.filter(is_deleted=True).count(), 2)

    def test_queryset_alive_and_dead(self):
        s1 = School.objects.create(name="Alive")
        s2 = School.objects.create(name="Dead")
        s2.delete()
        self.assertEqual(School.all_objects.filter(is_deleted=False).count(), 1)
        self.assertEqual(School.all_objects.filter(is_deleted=True).count(), 1)

    def test_deleted_at_is_set(self):
        school = School.objects.create(name="Timestamp")
        school.delete()
        school.refresh_from_db()
        self.assertIsNotNone(school.deleted_at)


class DateTimeUtilsTest(TestCase):
    """Tests for calendar and salary deadline helpers."""

    def test_calendar_month_range_january(self):
        start, end = calendar_month_range(2026, 1)
        self.assertEqual(start, date(2026, 1, 1))
        self.assertEqual(end, date(2026, 1, 31))

    def test_calendar_month_range_february_leap_year(self):
        start, end = calendar_month_range(2024, 2)
        self.assertEqual(start, date(2024, 2, 1))
        self.assertEqual(end, date(2024, 2, 29))

    def test_session_salary_deadline_48_hours(self):
        session_date = date(2026, 3, 15)
        deadline = session_salary_deadline(session_date)
        self.assertEqual(deadline.date(), date(2026, 3, 17))

    def test_is_salary_eligible_within_deadline(self):
        session_date = date(2026, 3, 15)
        approved_at = session_salary_deadline(session_date)
        self.assertTrue(is_salary_eligible(session_date, approved_at))

    def test_is_salary_eligible_after_deadline(self):
        session_date = date(2026, 3, 15)
        deadline = session_salary_deadline(session_date)
        late = deadline + __import__("datetime").timedelta(seconds=1)
        self.assertFalse(is_salary_eligible(session_date, late))


class ExceptionHandlerTest(TestCase):
    """Tests for structured error responses."""

    def test_validation_error_dict_format(self):
        exc = DRFValidationError({"field": ["error message"]})
        response = custom_exception_handler(exc, {"view": None})
        self.assertIn("error_code", response.data)
        self.assertIn("error_message", response.data)
        self.assertEqual(response.data["error_message"], {"field": ["error message"]})

    def test_validation_error_list_format(self):
        exc = DRFValidationError(["first error", "second error"])
        response = custom_exception_handler(exc, {"view": None})
        self.assertIn("first error", response.data["error_message"])

    def test_validation_error_string_format(self):
        exc = DRFValidationError("simple error")
        response = custom_exception_handler(exc, {"view": None})
        self.assertEqual(response.data["error_message"], "simple error")

    def test_validation_error_with_code_class(self):
        exc = ValidationErrorWithCode("custom message", code="custom_code")
        self.assertEqual(exc.default_code, "custom_code")


class SoftDeleteCascadeBehaviourTest(TestCase):
    """Verify soft-deleted parents still protect related records."""

    def test_classroom_still_references_soft_deleted_school(self):
        school = School.objects.create(name="School")
        term = Term.objects.create(
            name="Term",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        classroom = ClassRoom.objects.create(
            school=school,
            term=term,
            name="Class",
            session_duration=90,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        school.delete()
        classroom.refresh_from_db()
        self.assertEqual(classroom.school_id, school.id)

    def test_term_overlap_ignores_soft_deleted_terms(self):
        term1 = Term.objects.create(
            name="Term 1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
        )
        term1.delete()
        term2 = Term(
            name="Term 2",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 6, 30),
        )
        term2.full_clean()
        term2.save()
