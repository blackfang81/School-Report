from django.contrib import admin

from reports.models import SessionReport


@admin.register(SessionReport)
class SessionReportAdmin(admin.ModelAdmin):
    list_display = ("session_number", "classroom", "teacher", "session_date", "status", "is_salary_eligible")
