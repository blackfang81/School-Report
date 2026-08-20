from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0002_termbaserate_deleted_at_termbaserate_is_deleted"),
    ]

    operations = [
        migrations.AddField(
            model_name="salaryrecord",
            name="calculation_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="salaryrecord",
            name="period_end",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="salaryrecord",
            name="period_start",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterUniqueTogether(
            name="salaryrecord",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="salaryrecord",
            constraint=models.UniqueConstraint(
                condition=models.Q(("calculation_date__isnull", True)),
                fields=("teacher", "year", "month"),
                name="unique_teacher_calendar_month",
            ),
        ),
        migrations.AddConstraint(
            model_name="salaryrecord",
            constraint=models.UniqueConstraint(
                condition=models.Q(("calculation_date__isnull", False)),
                fields=("teacher", "calculation_date"),
                name="unique_teacher_calculation_date",
            ),
        ),
    ]
