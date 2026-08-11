"""Education domain models: schools, terms, classes, and teacher assignments."""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from accounts.models import Role, User
from config.mixins import SoftDeleteModel


class SessionDuration(models.IntegerChoices):
    """Allowed class session lengths in minutes."""

    MIN_60 = 60, "60 minutes"
    MIN_90 = 90, "90 minutes"
    MIN_120 = 120, "120 minutes"


class School(SoftDeleteModel):
    """A partner school where classes are held."""

    name = models.CharField(max_length=200)
    level = models.CharField(max_length=50, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    fax = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Term(SoftDeleteModel):
    """An academic term with a non-overlapping date range."""

    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    is_summer = models.BooleanField(default=False)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Run full validation on every save so ORM writes cannot create overlapping terms."""
        self.full_clean()
        return super().save(*args, **kwargs)

    def clean(self):
        """Validate date order and ensure no overlap with other terms."""
        if self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before start date."})

        overlap = Term.all_objects.filter(
            is_deleted=False,
            start_date__lte=self.end_date,
            end_date__gte=self.start_date,
        )
        if self.pk:
            overlap = overlap.exclude(pk=self.pk)
        if overlap.exists():
            raise ValidationError("Term date range overlaps with another term.")


class ClassRoom(SoftDeleteModel):
    """A class offered at a school during a specific term."""

    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="classes")
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name="classes")
    name = models.CharField(max_length=200)
    class_type = models.CharField(max_length=50, blank=True)
    session_duration = models.IntegerField(choices=SessionDuration.choices)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.name} ({self.school.name})"

    def clean(self):
        """Validate class dates and ensure they fall within the parent term."""
        if self.end_date < self.start_date:
            raise ValidationError({"end_date": "Class end date cannot be before start date."})

        if self.term_id:
            if self.start_date < self.term.start_date:
                raise ValidationError(
                    {"start_date": "Class start date must be within the term date range."}
                )
            if self.end_date > self.term.end_date:
                raise ValidationError(
                    {"end_date": "Class end date must be within the term date range."}
                )

    def get_active_teacher(self, target_date=None):
        """
        Return the teacher assignment active on ``target_date``.

        Defaults to today when no date is provided.
        """
        if target_date is None:
            target_date = timezone.localdate()
        for assignment in self.assignments.select_related("teacher").order_by("-start_date"):
            if assignment.is_active_on(target_date):
                return assignment
        return None

    def get_current_assignment(self, target_date=None):
        """
        Return the most relevant teacher assignment for display purposes.

        Prefers the assignment active on ``target_date``; for classes that have
        not started yet falls back to the nearest upcoming assignment, and for
        finished classes to the most recent one.
        """
        if target_date is None:
            target_date = timezone.localdate()
        assignments = list(self.assignments.select_related("teacher").order_by("start_date"))
        if not assignments:
            return None
        for assignment in assignments:
            if assignment.is_active_on(target_date):
                return assignment
        upcoming = [a for a in assignments if a.start_date > target_date]
        if upcoming:
            return upcoming[0]
        return assignments[-1]


class TeacherAssignment(SoftDeleteModel):
    """Links a teacher to a class for a specific date range."""

    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name="assignments")
    teacher = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        limit_choices_to={"role": Role.TEACHER},
        related_name="assignments",
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.teacher} -> {self.classroom}"

    def get_effective_end_date(self):
        """Return explicit end date or fall back to the class end date."""
        return self.end_date or self.classroom.end_date

    def clean(self):
        """Validate date order and prevent overlapping assignments on the same class."""
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before start date."})

        if self.classroom_id and self.start_date < self.classroom.start_date:
            raise ValidationError(
                {"start_date": "Assignment start date must be within the class date range."}
            )

        effective_end = self.get_effective_end_date()
        if self.classroom_id and effective_end > self.classroom.end_date:
            raise ValidationError(
                {"end_date": "Assignment end date must be within the class date range."}
            )

        qs = TeacherAssignment.all_objects.filter(
            classroom=self.classroom,
            is_deleted=False,
        )
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        start = self.start_date
        end = effective_end

        for other in qs:
            other_end = other.get_effective_end_date()
            if start <= other_end and end >= other.start_date:
                raise ValidationError(
                    "Date range overlaps with another teacher assignment for this class."
                )

    def is_active_on(self, target_date):
        """Return True when this assignment covers ``target_date``."""
        if target_date < self.start_date:
            return False
        effective_end = self.get_effective_end_date()
        if target_date > effective_end:
            return False
        return True
