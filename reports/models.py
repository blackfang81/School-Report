from django.db import models
from config.project_clock import project_now

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
    class_session = models.ForeignKey(
        "education.ClassSession",
        on_delete=models.PROTECT,
        related_name="reports",
        null=True,
        blank=True,
    )
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
    submitted_at = models.DateTimeField(default=project_now)
    updated_at = models.DateTimeField(default=project_now)
    approved_at = models.DateTimeField(null=True, blank=True)
    is_salary_eligible = models.BooleanField(default=False)

    class Meta:
        ordering = ["-session_date", "-session_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["classroom", "session_number"],
                condition=models.Q(is_deleted=False),
                name="unique_active_session_number_per_classroom",
            ),
            models.UniqueConstraint(
                fields=["class_session"],
                condition=models.Q(is_deleted=False),
                name="unique_active_report_per_class_session",
            ),
        ]

    def __str__(self):
        return f"Session {self.session_number} - {self.classroom.name}"

    def save(self, *args, **kwargs):
        now = project_now()
        if self._state.adding:
            self.submitted_at = now
        self.updated_at = now
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            fields = set(update_fields)
            fields.add("updated_at")
            if self._state.adding:
                fields.add("submitted_at")
            kwargs["update_fields"] = fields
        super().save(*args, **kwargs)

    @staticmethod
    def next_session_number(classroom):
        last = (
            SessionReport.objects.filter(classroom=classroom)
            .order_by("-session_number")
            .first()
        )
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

    @staticmethod
    def validate_class_session_for_teacher(teacher, class_session):
        """Ensure the session belongs to the teacher's assignment and has no report yet."""
        if class_session.is_deleted:
            raise ValueError("Session is not available.")

        classroom = class_session.classroom
        if not SessionReport.teacher_owns_class_on_date(
            teacher, classroom, class_session.session_date
        ):
            raise ValueError("You are not assigned to this class on the selected session date.")

        if class_session.reports.filter(is_deleted=False).exists():
            raise ValueError("A report already exists for this session.")

    def mark_approved(self):
        now = project_now()
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
