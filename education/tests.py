from datetime import date

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, User
from education.models import ClassRoom, School, TeacherAssignment, Term


class EducationModelTest(TestCase):
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
        with self.assertRaises(Exception):
            assignment.full_clean()


class EducationAPITest(APITestCase):
    def setUp(self):
        self.officer = User.objects.create_user(
            username="officer", password="pass12345", role=Role.EDUCATION_OFFICER
        )
        token = RefreshToken.for_user(self.officer).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_create_school(self):
        response = self.client.post(
            reverse("school-list"),
            {"name": "New School", "phone": "02111111111"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_class_invalid_duration(self):
        school = School.objects.create(name="s1")
        term = Term.objects.create(
            name="t1",
            start_date=date(2026, 9, 23),
            end_date=date(2027, 6, 21),
        )
        response = self.client.post(
            reverse("class-list"),
            {
                "school": school.id,
                "term": term.id,
                "name": "Class",
                "session_duration": 45,
                "start_date": "2026-09-01",
                "end_date": "2027-06-30",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
