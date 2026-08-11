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
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("teacher", "year", "month")
        ordering = ["-year", "-month"]

    def __str__(self):
        return f"{self.teacher} - {self.year}/{self.month:02d}"
