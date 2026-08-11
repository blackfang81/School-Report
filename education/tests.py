"""Tests for education app: models, validation, API CRUD, and access scoping."""

from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, User
from education.models import ClassRoom, School, TeacherAssignment, Term


class EducationModelTest(TestCase):
    """Unit tests for education domain models."""

    def setUp(self):
        self.school = School.objects.create(name="School 1")
        self.term = Term.objects.create(
            name="Term 1",
            start_date=date(2026, 9, 23),
            end_date=date(2027, 6, 21),
        )
        self.teacher = User.objects.create_user(
            username="t1", password="pass12345", role=Role.TEACHER
        )

    def test_term_end_before_start(self):
        term = Term(name="Bad", start_date=date(2027, 1, 1), end_date=date(2026, 1, 1))
        with self.assertRaises(ValidationError):
            term.full_clean()

    def test_term_overlap(self):
        with self.assertRaises(ValidationError):
            Term.objects.create(
                name="Overlap",
                start_date=date(2026, 10, 1),
                end_date=date(2027, 1, 1),
            )

    def test_class_outside_term_dates(self):
        classroom = ClassRoom(
            school=self.school,
            term=self.term,
            name="Bad Class",
            session_duration=90,
            start_date=date(2026, 8, 1),
            end_date=date(2027, 6, 21),
        )
        with self.assertRaises(ValidationError):
            classroom.full_clean()

    def test_teacher_assignment_overlap(self):
        classroom = ClassRoom.objects.create(
            school=self.school,
            term=self.term,
            name="Class A",
            session_duration=90,
            start_date=date(2026, 9, 23),
            end_date=date(2027, 6, 21),
        )
        t2 = User.objects.create_user(username="t2", password="pass12345", role=Role.TEACHER)
        TeacherAssignment.objects.create(
            classroom=classroom,
            teacher=self.teacher,
            start_date=date(2026, 9, 23),
            end_date=date(2026, 10, 23),
        )
        assignment = TeacherAssignment(
            classroom=classroom,
            teacher=t2,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 11, 1),
        )
        with self.assertRaises(ValidationError):
            assignment.full_clean()

    def test_sequential_teachers_no_overlap(self):
        classroom = ClassRoom.objects.create(
            school=self.school,
            term=self.term,
            name="Class A",
            session_duration=90,
            start_date=date(2026, 9, 23),
            end_date=date(2027, 6, 21),
        )
        t2 = User.objects.create_user(username="t2", password="pass12345", role=Role.TEACHER)
        TeacherAssignment.objects.create(
            classroom=classroom,
            teacher=self.teacher,
            start_date=date(2026, 9, 23),
            end_date=date(2026, 10, 31),
        )
        assignment = TeacherAssignment(
            classroom=classroom,
            teacher=t2,
            start_date=date(2026, 11, 1),
            end_date=date(2027, 6, 21),
        )
        assignment.full_clean()
        assignment.save()
        self.assertEqual(classroom.assignments.count(), 2)

    def test_assignment_implicit_end_date(self):
        classroom = ClassRoom.objects.create(
            school=self.school,
            term=self.term,
            name="Class A",
            session_duration=90,
            start_date=date(2026, 9, 23),
            end_date=date(2027, 6, 21),
        )
        assignment = TeacherAssignment.objects.create(
            classroom=classroom,
            teacher=self.teacher,
            start_date=date(2026, 9, 23),
        )
        self.assertTrue(assignment.is_active_on(date(2027, 6, 21)))
        self.assertFalse(assignment.is_active_on(date(2027, 7, 1)))

    def test_soft_delete_school(self):
        school = School.objects.create(name="To Delete")
        school_id = school.id
        school.delete()
        self.assertFalse(School.objects.filter(id=school_id).exists())
        self.assertTrue(School.all_objects.filter(id=school_id, is_deleted=True).exists())


class EducationAPITest(APITestCase):
    """API integration tests for education endpoints."""

    def setUp(self):
        self.officer = User.objects.create_user(
            username="officer", password="pass12345", role=Role.EDUCATION_OFFICER
        )
        self.teacher1 = User.objects.create_user(
            username="teacher1",
            password="pass12345",
            role=Role.TEACHER,
            first_name="Teacher",
            last_name="One",
        )
        self.teacher2 = User.objects.create_user(
            username="teacher2", password="pass12345", role=Role.TEACHER
        )
        self.school = School.objects.create(name="School 1", phone="02111111111")
        self.term = Term.objects.create(
            name="Term 1",
            start_date=date(2026, 9, 23),
            end_date=date(2027, 6, 21),
        )
        self.classroom = ClassRoom.objects.create(
            school=self.school,
            term=self.term,
            name="Class A",
            session_duration=90,
            start_date=date(2026, 9, 23),
            end_date=date(2027, 6, 21),
        )
        TeacherAssignment.objects.create(
            classroom=self.classroom,
            teacher=self.teacher1,
            start_date=date(2026, 9, 23),
        )

    def auth(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_create_school(self):
        self.auth(self.officer)
        response = self.client.post(
            reverse("school-list"),
            {"name": "New School", "phone": "02122222222"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(School.objects.count(), 2)

    def test_update_school(self):
        self.auth(self.officer)
        response = self.client.patch(
            reverse("school-detail", args=[self.school.id]),
            {"phone": "02199999999"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.school.refresh_from_db()
        self.assertEqual(self.school.phone, "02199999999")

    def test_soft_delete_school(self):
        self.auth(self.officer)
        response = self.client.delete(reverse("school-detail", args=[self.school.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.school.refresh_from_db()
        self.assertTrue(self.school.is_deleted)

    def test_create_term(self):
        self.auth(self.officer)
        response = self.client.post(
            reverse("term-list"),
            {
                "name": "Summer 2027",
                "start_date": "2027-07-01",
                "end_date": "2027-08-31",
                "is_summer": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_overlapping_term_fails(self):
        self.auth(self.officer)
        response = self.client.post(
            reverse("term-list"),
            {
                "name": "Overlap Term",
                "start_date": "2026-10-01",
                "end_date": "2027-01-01",
                "is_summer": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_class_invalid_duration(self):
        self.auth(self.officer)
        response = self.client.post(
            reverse("class-list"),
            {
                "school": self.school.id,
                "term": self.term.id,
                "name": "Bad Class",
                "session_duration": 45,
                "start_date": "2026-09-23",
                "end_date": "2027-06-21",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_class_outside_term_fails(self):
        self.auth(self.officer)
        response = self.client.post(
            reverse("class-list"),
            {
                "school": self.school.id,
                "term": self.term.id,
                "name": "Bad Dates",
                "session_duration": 90,
                "start_date": "2026-08-01",
                "end_date": "2027-06-21",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_class_detail_includes_current_teacher(self):
        self.auth(self.officer)
        response = self.client.get(reverse("class-detail", args=[self.classroom.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data["current_teacher"])
        self.assertEqual(response.data["current_teacher"]["teacher_id"], self.teacher1.id)

    def test_filter_classes_by_teacher(self):
        self.auth(self.officer)
        response = self.client.get(
            reverse("class-list"), {"teacher": self.teacher1.id}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_search_schools_by_name(self):
        self.auth(self.officer)
        response = self.client.get(reverse("school-list"), {"search": "School 1"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_teacher_sees_only_own_classes(self):
        other_class = ClassRoom.objects.create(
            school=self.school,
            term=self.term,
            name="Class B",
            session_duration=60,
            start_date=date(2026, 9, 23),
            end_date=date(2027, 6, 21),
        )
        TeacherAssignment.objects.create(
            classroom=other_class,
            teacher=self.teacher2,
            start_date=date(2026, 9, 23),
        )

        self.auth(self.teacher1)
        response = self.client.get(reverse("class-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in response.data["results"]]
        self.assertIn(self.classroom.id, ids)
        self.assertNotIn(other_class.id, ids)

    def test_teacher_sees_only_own_assignments(self):
        self.auth(self.teacher1)
        response = self.client.get(reverse("teacher-assignment-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["teacher"], self.teacher1.id)

    def test_create_assignment_overlap_returns_400(self):
        self.auth(self.officer)
        response = self.client.post(
            reverse("teacher-assignment-list"),
            {
                "classroom": self.classroom.id,
                "teacher": self.teacher2.id,
                "start_date": "2026-09-23",
                "end_date": "2026-12-31",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sequential_multi_teacher_via_api(self):
        """Tir/Mordad scenario: teacher A then teacher B without overlap."""
        self.auth(self.officer)
        response = self.client.patch(
            reverse("teacher-assignment-detail", args=[
                TeacherAssignment.objects.get(classroom=self.classroom).id
            ]),
            {"end_date": "2026-10-31"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        response = self.client.post(
            reverse("teacher-assignment-list"),
            {
                "classroom": self.classroom.id,
                "teacher": self.teacher2.id,
                "start_date": "2026-11-01",
                "end_date": "2027-06-21",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.classroom.assignments.count(), 2)

    def test_teacher_cannot_create_assignment(self):
        self.auth(self.teacher1)
        response = self.client.post(
            reverse("teacher-assignment-list"),
            {
                "classroom": self.classroom.id,
                "teacher": self.teacher1.id,
                "start_date": "2026-09-23",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_assign_non_teacher_role_fails(self):
        finance = User.objects.create_user(
            username="finance", password="pass12345", role=Role.FINANCE_OFFICER
        )
        self.auth(self.officer)
        response = self.client.post(
            reverse("teacher-assignment-list"),
            {
                "classroom": self.classroom.id,
                "teacher": finance.id,
                "start_date": "2026-09-23",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_soft_delete_term(self):
        self.auth(self.officer)
        term = Term.objects.create(
            name="Delete Me",
            start_date=date(2028, 1, 1),
            end_date=date(2028, 6, 30),
        )
        response = self.client.delete(reverse("term-detail", args=[term.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        term.refresh_from_db()
        self.assertTrue(term.is_deleted)

    def test_soft_delete_class(self):
        self.auth(self.officer)
        response = self.client.delete(reverse("class-detail", args=[self.classroom.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.classroom.refresh_from_db()
        self.assertTrue(self.classroom.is_deleted)

    def test_soft_delete_assignment(self):
        assignment = TeacherAssignment.objects.get(classroom=self.classroom)
        self.auth(self.officer)
        response = self.client.delete(
            reverse("teacher-assignment-detail", args=[assignment.id])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        assignment.refresh_from_db()
        self.assertTrue(assignment.is_deleted)

    def test_deleted_school_not_in_list(self):
        self.auth(self.officer)
        school2 = School.objects.create(name="Temp School")
        self.client.delete(reverse("school-detail", args=[school2.id]))
        response = self.client.get(reverse("school-list"))
        ids = [s["id"] for s in response.data["results"]]
        self.assertNotIn(school2.id, ids)

    def test_teacher_can_read_schools(self):
        self.auth(self.teacher1)
        response = self.client.get(reverse("school-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_teacher_cannot_delete_school(self):
        self.auth(self.teacher1)
        response = self.client.delete(reverse("school-detail", args=[self.school.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_filter_classes_by_school(self):
        self.auth(self.officer)
        response = self.client.get(
            reverse("class-list"), {"school": self.school.id}
        )
        self.assertEqual(len(response.data["results"]), 1)

    def test_filter_classes_by_term(self):
        self.auth(self.officer)
        response = self.client.get(
            reverse("class-list"), {"term": self.term.id}
        )
        self.assertEqual(len(response.data["results"]), 1)

    def test_filter_classes_by_session_duration(self):
        self.auth(self.officer)
        response = self.client.get(
            reverse("class-list"), {"session_duration": 90}
        )
        self.assertEqual(len(response.data["results"]), 1)
        response = self.client.get(
            reverse("class-list"), {"session_duration": 60}
        )
        self.assertEqual(len(response.data["results"]), 0)

    def test_class_get_current_assignment_upcoming(self):
        """Before class starts, current_teacher should be the upcoming assignment."""
        future_term = Term.objects.create(
            name="Future",
            start_date=date(2028, 1, 1),
            end_date=date(2028, 6, 30),
        )
        future_class = ClassRoom.objects.create(
            school=self.school,
            term=future_term,
            name="Future Class",
            session_duration=90,
            start_date=date(2028, 1, 1),
            end_date=date(2028, 6, 30),
        )
        TeacherAssignment.objects.create(
            classroom=future_class,
            teacher=self.teacher1,
            start_date=date(2028, 1, 1),
        )
        self.auth(self.officer)
        response = self.client.get(reverse("class-detail", args=[future_class.id]))
        self.assertIsNotNone(response.data["current_teacher"])
        self.assertEqual(response.data["current_teacher"]["teacher_id"], self.teacher1.id)
