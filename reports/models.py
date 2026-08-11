from django.db import models
from django.utils import timezone

from accounts.models import User
from config.datetime_utils import is_salary_eligible
from config.mixins import SoftDeleteModel
from education.models import ClassRoom, TeacherAssignment


class ReportStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class SessionReport(SoftDeleteModel):
    classroom = models.ForeignKey(ClassRoom, on_delete=models.PROTECT, related_name="reports")
    teacher = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        limit_choices_to={"role": "teacher"},
        related_name="session_reports",
    )
    session_date = models.DateField()
    session_number = models.PositiveIntegerField()
    summary = models.TextField()
    present_count = models.PositiveIntegerField()
    absent_count = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=ReportStatus.choices,
        default=ReportStatus.PENDING,
    )
    officer_note = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    is_salary_eligible = models.BooleanField(default=False)

    class Meta:
        ordering = ["-session_date", "-session_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["classroom", "session_number"],
                condition=models.Q(is_deleted=False),
                name="unique_active_session_number_per_classroom",
            )
        ]

    def __str__(self):
        return f"Session {self.session_number} - {self.classroom.name}"

    @staticmethod
    def next_session_number(classroom):
        last = SessionReport.objects.filter(classroom=classroom).order_by("-session_number").first()
        return (last.session_number + 1) if last else 1

    @staticmethod
    def teacher_owns_class_on_date(teacher, classroom, session_date):
        return TeacherAssignment.objects.filter(
            classroom=classroom,
            teacher=teacher,
            start_date__lte=session_date,
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=session_date)
        ).exists()

    def mark_approved(self):
        now = timezone.now()
        self.status = ReportStatus.APPROVED
        self.approved_at = now
        self.is_salary_eligible = is_salary_eligible(self.session_date, now)
        self.save(
            update_fields=["status", "approved_at", "is_salary_eligible", "updated_at"]
        )

    def mark_rejected(self, note=""):
        self.status = ReportStatus.REJECTED
        self.officer_note = note
        self.approved_at = None
        self.is_salary_eligible = False
        self.save(
            update_fields=["status", "officer_note", "approved_at", "is_salary_eligible", "updated_at"]
        )
