"""Education domain models: schools, terms, classes, and teacher assignments."""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from config.project_clock import project_localdate

from accounts.models import Role, User
from config.datetime_utils import is_first_day_of_month, is_last_day_of_month
from config.mixins import SoftDeleteModel
from education.session_utils import build_session_plan


class SessionDuration(models.IntegerChoices):
    """Allowed class session lengths in minutes."""

    MIN_60 = 60, "60 minutes"
    MIN_90 = 90, "90 minutes"
    MIN_120 = 120, "120 minutes"


class Weekday(models.IntegerChoices):
    """Weekdays using Python's ``date.weekday()`` convention."""

    MONDAY = 0, "Monday"
    TUESDAY = 1, "Tuesday"
    WEDNESDAY = 2, "Wednesday"
    THURSDAY = 3, "Thursday"
    FRIDAY = 4, "Friday"
    SATURDAY = 5, "Saturday"
    SUNDAY = 6, "Sunday"


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
        constraints = [
            models.UniqueConstraint(
                fields=["phone"],
                condition=Q(is_deleted=False) & ~Q(phone=""),
                name="unique_active_school_phone",
            )
        ]

    def __str__(self):
        return self.name

    def clean(self):
        phone = (self.phone or "").strip()
        if not phone:
            return

        duplicate = School.all_objects.filter(phone=phone, is_deleted=False)
        if self.pk:
            duplicate = duplicate.exclude(pk=self.pk)
        if duplicate.exists():
            raise ValidationError({"phone": "Another school already uses this phone number."})


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
        """Validate date order, month boundaries, and ensure no overlap with other terms."""
        if self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before start date."})

        if not is_first_day_of_month(self.start_date):
            raise ValidationError(
                {"start_date": "Term must start on the first day of a month."}
            )

        if not is_last_day_of_month(self.end_date):
            raise ValidationError(
                {"end_date": "Term must end on the last day of a month."}
            )

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

    def get_weekdays(self):
        """Return active weekday integers configured for this class."""
        return list(
            self.weekdays.filter(is_deleted=False)
            .order_by("weekday")
            .values_list("weekday", flat=True)
        )

    def regenerate_sessions(self):
        """
        Rebuild scheduled sessions from current dates and weekday pattern.

        Sessions that already have reports are preserved; unreported sessions are replaced.
        """
        from education.models import ClassSession

        weekdays = self.get_weekdays()
        plan = build_session_plan(self.start_date, self.end_date, weekdays)

        existing = {
            session.session_number: session
            for session in ClassSession.all_objects.filter(classroom=self, is_deleted=False)
        }
        reported_numbers = set(
            self.reports.filter(is_deleted=False).values_list("session_number", flat=True)
        )

        planned_numbers = {number for number, _ in plan}
        for number, session in existing.items():
            if number in reported_numbers:
                continue
            if number not in planned_numbers:
                session.delete()

        for number, session_date in plan:
            session = existing.get(number)
            if number in reported_numbers and session:
                if session.session_date != session_date:
                    raise ValidationError(
                        "Cannot change schedule for a session that already has a report."
                    )
                continue

            if session:
                if session.is_deleted:
                    session.restore()
                session.session_date = session_date
                session.save(update_fields=["session_date"])
                continue

            ClassSession.objects.create(
                classroom=self,
                session_number=number,
                session_date=session_date,
            )

    def get_active_teacher(self, target_date=None):
        """
        Return the teacher assignment active on ``target_date``.

        Defaults to today when no date is provided.
        """
        if target_date is None:
            target_date = project_localdate()
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
            target_date = project_localdate()
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


class ClassRoomWeekday(SoftDeleteModel):
    """A weekday on which a class meets during its date range."""

    classroom = models.ForeignKey(
        ClassRoom, on_delete=models.CASCADE, related_name="weekdays"
    )
    weekday = models.IntegerField(choices=Weekday.choices)

    class Meta:
        ordering = ["weekday"]
        constraints = [
            models.UniqueConstraint(
                fields=["classroom", "weekday"],
                condition=models.Q(is_deleted=False),
                name="unique_active_weekday_per_classroom",
            )
        ]

    def __str__(self):
        return f"{self.classroom.name} - {self.get_weekday_display()}"


class ClassSession(SoftDeleteModel):
    """A scheduled session slot generated from a class weekly pattern."""

    classroom = models.ForeignKey(
        ClassRoom, on_delete=models.CASCADE, related_name="sessions"
    )
    session_number = models.PositiveIntegerField()
    session_date = models.DateField()

    class Meta:
        ordering = ["session_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["classroom", "session_number"],
                condition=models.Q(is_deleted=False),
                name="unique_active_class_session_number",
            ),
            models.UniqueConstraint(
                fields=["classroom", "session_date"],
                condition=models.Q(is_deleted=False),
                name="unique_active_class_session_date",
            ),
        ]

    def __str__(self):
        return f"{self.classroom.name} - Session {self.session_number}"

    @property
    def has_report(self):
        return self.reports.filter(is_deleted=False).exists()
