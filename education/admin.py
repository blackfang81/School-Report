from django.contrib import admin

from .models import ClassRoom, School, TeacherAssignment, Term


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "level", "phone")


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "is_summer")


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ("name", "school", "term", "session_duration")


@admin.register(TeacherAssignment)
class TeacherAssignmentAdmin(admin.ModelAdmin):
    list_display = ("classroom", "teacher", "start_date", "end_date")
