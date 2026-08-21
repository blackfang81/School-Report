"""Tests for accounts app: models, auth, permissions, and management commands."""

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, User
from education.models import ClassRoom, ClassSession
from finance.models import TermBaseRate


class UserModelTest(TestCase):
    """Unit tests for the custom User model."""

    def test_user_roles(self):
        teacher = User.objects.create_user(
            username="t1", password="pass12345", role=Role.TEACHER
        )
        officer = User.objects.create_user(
            username="o1", password="pass12345", role=Role.EDUCATION_OFFICER
        )
        finance = User.objects.create_user(
            username="f1", password="pass12345", role=Role.FINANCE_OFFICER
        )
        self.assertTrue(teacher.is_teacher)
        self.assertFalse(teacher.is_education_officer)
        self.assertTrue(officer.is_education_officer)
        self.assertTrue(finance.is_finance_officer)

    def test_user_str(self):
        user = User.objects.create_user(
            username="ali",
            password="pass12345",
            role=Role.TEACHER,
            first_name="Ali",
            last_name="Ahmadi",
        )
        self.assertIn("Ali Ahmadi", str(user))
        self.assertIn("Teacher", str(user))


class CreateUserCommandTest(TestCase):
    """Tests for the create_user management command."""

    def test_create_teacher(self):
        out = StringIO()
        call_command(
            "create_user",
            username="newteacher",
            password="pass12345",
            role=Role.TEACHER,
            first_name="New",
            last_name="Teacher",
            phone="09121111111",
            stdout=out,
        )
        user = User.objects.get(username="newteacher")
        self.assertEqual(user.role, Role.TEACHER)
        self.assertEqual(user.phone, "09121111111")
        self.assertTrue(user.check_password("pass12345"))

    def test_create_staff_user(self):
        call_command(
            "create_user",
            username="staffuser",
            password="pass12345",
            role=Role.EDUCATION_OFFICER,
            staff=True,
        )
        user = User.objects.get(username="staffuser")
        self.assertTrue(user.is_staff)

    def test_duplicate_username_raises(self):
        User.objects.create_user(username="dup", password="pass12345", role=Role.TEACHER)
        with self.assertRaises(CommandError):
            call_command(
                "create_user",
                username="dup",
                password="pass12345",
                role=Role.TEACHER,
            )


class ResetPasswordCommandTest(TestCase):
    """Tests for the reset_password management command."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="resetme", password="oldpass123", role=Role.TEACHER
        )

    def test_reset_password(self):
        call_command("reset_password", username="resetme", password="newpass123")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass123"))

    def test_unknown_user_raises(self):
        with self.assertRaises(CommandError):
            call_command("reset_password", username="nobody", password="newpass123")


class SeedDataCommandTest(TestCase):
    """Tests for the seed_data management command."""

    def test_seed_data_is_idempotent(self):
        out1 = StringIO()
        call_command("seed_data", stdout=out1)
        self.assertTrue(User.objects.filter(username="teacher1").exists())
        self.assertTrue(User.objects.filter(username="teacher2").exists())
        self.assertTrue(User.objects.filter(username="admin1").exists())
        self.assertTrue(ClassRoom.objects.filter(name="Robotics").exists())
        self.assertGreater(ClassSession.objects.filter(is_deleted=False).count(), 0)
        self.assertEqual(TermBaseRate.objects.filter(is_deleted=False).count(), 2)

        out2 = StringIO()
        call_command("seed_data", stdout=out2)
        self.assertEqual(User.objects.filter(username="teacher1").count(), 1)
        self.assertIn("already exists", out2.getvalue())


class AuthAccessTest(APITestCase):
    """API tests for authentication, role checks, and access control."""

    def setUp(self):
        self.teacher = User.objects.create_user(
            username="teacher",
            password="pass12345",
            role=Role.TEACHER,
            first_name="Ali",
            last_name="Teacher",
            phone="09121111111",
            emergency_phone="09122222222",
        )
        self.officer = User.objects.create_user(
            username="officer",
            password="pass12345",
            role=Role.EDUCATION_OFFICER,
        )
        self.finance = User.objects.create_user(
            username="finance",
            password="pass12345",
            role=Role.FINANCE_OFFICER,
        )
        self.admin = User.objects.create_user(
            username="admin",
            password="pass12345",
            role=Role.EDUCATION_OFFICER,
            is_staff=True,
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
        self.assertIn("refresh", response.data)

    def test_login_invalid_credentials(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "teacher", "password": "wrong"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_role_check(self):
        self.auth(self.teacher)
        response = self.client.get(reverse("role_check"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["role"], Role.TEACHER)
        self.assertTrue(response.data["is_teacher"])
        self.assertFalse(response.data["is_staff"])

    def test_me_get(self):
        self.auth(self.teacher)
        response = self.client.get(reverse("me"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "teacher")
        self.assertEqual(response.data["phone"], "09121111111")

    def test_profile_update(self):
        self.auth(self.teacher)
        response = self.client.patch(
            reverse("me"),
            {"first_name": "John", "phone": "09123333333"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.first_name, "John")
        self.assertEqual(self.teacher.phone, "09123333333")

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

    def test_change_password_wrong_old(self):
        self.auth(self.teacher)
        response = self.client.post(
            reverse("change_password"),
            {"old_password": "wrong", "new_password": "newpass123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_teacher_cannot_access_finance_rates(self):
        self.auth(self.teacher)
        response = self.client.get("/api/finance/base-rates/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_finance_can_access_rates(self):
        self.auth(self.finance)
        response = self.client.get("/api/finance/base-rates/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_teacher_cannot_create_school(self):
        self.auth(self.teacher)
        response = self.client.post(
            reverse("school-list"),
            {"name": "Hacked School"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_finance_cannot_create_school(self):
        self.auth(self.finance)
        response = self.client.post(
            reverse("school-list"),
            {"name": "Hacked School"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_list_officer_only(self):
        self.auth(self.teacher)
        response = self.client.get(reverse("teacher_list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.auth(self.officer)
        response = self.client.get(reverse("teacher_list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_admin_create_user_via_api(self):
        self.auth(self.admin)
        response = self.client.post(
            reverse("admin_create_user"),
            {
                "username": "created",
                "password": "pass12345",
                "role": Role.TEACHER,
                "first_name": "Created",
                "last_name": "User",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username="created").exists())

    def test_non_staff_cannot_create_user_via_api(self):
        self.auth(self.officer)
        response = self.client.post(
            reverse("admin_create_user"),
            {
                "username": "blocked",
                "password": "pass12345",
                "role": Role.TEACHER,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_access_me(self):
        response = self.client.get(reverse("me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh(self):
        refresh = RefreshToken.for_user(self.teacher)
        response = self.client.post(
            reverse("token_refresh"),
            {"refresh": str(refresh)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_role_check_for_officer(self):
        self.auth(self.officer)
        response = self.client.get(reverse("role_check"))
        self.assertEqual(response.data["role"], Role.EDUCATION_OFFICER)
        self.assertTrue(response.data["is_education_officer"])

    def test_role_check_for_finance(self):
        self.auth(self.finance)
        response = self.client.get(reverse("role_check"))
        self.assertTrue(response.data["is_finance_officer"])

    def test_role_check_for_admin(self):
        self.auth(self.admin)
        response = self.client.get(reverse("role_check"))
        self.assertTrue(response.data["is_staff"])

    def test_me_put_update(self):
        self.auth(self.teacher)
        response = self.client.put(
            reverse("me"),
            {
                "first_name": "Updated",
                "last_name": "Name",
                "phone": "09124444444",
                "emergency_phone": "09125555555",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.first_name, "Updated")

    def test_change_password_too_short(self):
        self.auth(self.teacher)
        response = self.client.post(
            reverse("change_password"),
            {"old_password": "pass12345", "new_password": "short"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_create_user_invalid_role(self):
        self.auth(self.admin)
        response = self.client.post(
            reverse("admin_create_user"),
            {
                "username": "badrole",
                "password": "pass12345",
                "role": "invalid_role",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_teacher_list_excludes_inactive(self):
        User.objects.create_user(
            username="inactive",
            password="pass12345",
            role=Role.TEACHER,
            is_active=False,
        )
        self.auth(self.officer)
        response = self.client.get(reverse("teacher_list"))
        self.assertEqual(len(response.data["results"]), 1)

    def test_teacher_list_excludes_non_teachers(self):
        self.auth(self.officer)
        response = self.client.get(reverse("teacher_list"))
        usernames = [u["username"] for u in response.data["results"]]
        self.assertNotIn("officer", usernames)
        self.assertNotIn("finance", usernames)

    def test_finance_cannot_create_user(self):
        self.auth(self.finance)
        response = self.client.post(
            reverse("admin_create_user"),
            {
                "username": "blocked2",
                "password": "pass12345",
                "role": Role.TEACHER,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
