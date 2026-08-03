from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
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
        return self.role == Role.TEACHER

    @property
    def is_education_officer(self):
        return self.role == Role.EDUCATION_OFFICER

    @property
    def is_finance_officer(self):
        return self.role == Role.FINANCE_OFFICER
