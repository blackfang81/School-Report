from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, User


class UserModelTest(TestCase):
    def test_user_roles(self):
        teacher = User.objects.create_user(
            username="t1", password="pass12345", role=Role.TEACHER
        )
        self.assertTrue(teacher.is_teacher)
        self.assertFalse(teacher.is_education_officer)


class AuthAccessTest(APITestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username="teacher", password="pass12345", role=Role.TEACHER
        )
        self.officer = User.objects.create_user(
            username="officer", password="pass12345", role=Role.EDUCATION_OFFICER
        )
        self.finance = User.objects.create_user(
            username="finance", password="pass12345", role=Role.FINANCE_OFFICER
        )

    def auth(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_login_returns_token(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "teacher", "password": "pass12345"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_profile_update(self):
        self.auth(self.teacher)
        response = self.client.patch(
            reverse("me"),
            {"first_name": "John", "phone": "09121111111"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.first_name, "John")

    def test_change_password(self):
        self.auth(self.teacher)
        response = self.client.post(
            reverse("change_password"),
            {"old_password": "pass12345", "new_password": "newpass123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.teacher.refresh_from_db()
        self.assertTrue(self.teacher.check_password("newpass123"))
