"""Custom user model and role definitions."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    """System roles with distinct access boundaries."""

    TEACHER = "teacher", "Teacher"
    EDUCATION_OFFICER = "education_officer", "Education Officer"
    FINANCE_OFFICER = "finance_officer", "Finance Officer"


class User(AbstractUser):
    """
    Application user with a single assigned role.

    Staff users (``is_staff=True``) can access Django admin and the user-creation API.
    Deactivation uses ``is_active=False`` instead of hard delete.
    """

    role = models.CharField(max_length=30, choices=Role.choices)
    phone = models.CharField(max_length=20, blank=True)
    emergency_phone = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_teacher(self):
        """True when the user has the teacher role."""
        return self.role == Role.TEACHER

    @property
    def is_education_officer(self):
        """True when the user has the education officer role."""
        return self.role == Role.EDUCATION_OFFICER

    @property
    def is_finance_officer(self):
        """True when the user has the finance officer role."""
        return self.role == Role.FINANCE_OFFICER
