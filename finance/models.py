from django.db import models

from config.mixins import SoftDeleteModel


class TermBaseRate(SoftDeleteModel):
    term = models.OneToOneField("education.Term", on_delete=models.CASCADE, related_name="base_rate")
    base_rate = models.DecimalField(max_digits=12, decimal_places=0)

    def __str__(self):
        return f"{self.term.name}: {self.base_rate}"


class SalaryRecord(models.Model):
    teacher = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="salaries")
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=14, decimal_places=0)
    calculation_date = models.DateField(null=True, blank=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("teacher", "year", "month"),
                condition=models.Q(calculation_date__isnull=True),
                name="unique_teacher_calendar_month",
            ),
            models.UniqueConstraint(
                fields=("teacher", "calculation_date"),
                condition=models.Q(calculation_date__isnull=False),
                name="unique_teacher_calculation_date",
            ),
        ]
        ordering = ["-calculation_date", "-year", "-month"]

    def __str__(self):
        if self.calculation_date:
            return f"{self.teacher} - calc {self.calculation_date}"
        return f"{self.teacher} - {self.year}/{self.month:02d}"
