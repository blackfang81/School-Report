from django.core.exceptions import ValidationError
from django.db import models

# Create your models here.
class School(models.Model):
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


class Term(models.Model):
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    is_summer = models.BooleanField(default=False)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError("End date cannot be before start date.")

        overlap = Term.objects.filter(
            Q(start_date__lte=self.end_date) & Q(end_date__gte=self.start_date)
        )
        if self.pk:
            overlap = overlap.exclude(pk=self.pk)
        if overlap.exists():
            raise ValidationError("Term date range overlaps with another term.")


class ClassRoom(models.Model):
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
        if self.end_date < self.start_date:
            raise ValidationError("Class end date cannot be before start date.")
