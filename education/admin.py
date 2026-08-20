from django.contrib import admin

from .models import ClassRoom, ClassRoomWeekday, ClassSession, School, TeacherAssignment, Term


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("name", "level", "phone", "is_deleted")
    list_filter = ("is_deleted",)
    search_fields = ("name", "phone")


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "is_summer", "is_deleted")
    list_filter = ("is_summer", "is_deleted")
    search_fields = ("name",)


class ClassRoomWeekdayInline(admin.TabularInline):
    model = ClassRoomWeekday
    extra = 1


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ("name", "school", "term", "session_duration", "is_deleted")
    list_filter = ("session_duration", "is_deleted", "term", "school")
    search_fields = ("name",)
    inlines = [ClassRoomWeekdayInline]


@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = ("classroom", "session_number", "session_date", "is_deleted")
    list_filter = ("is_deleted", "classroom__term")
    search_fields = ("classroom__name",)


@admin.register(TeacherAssignment)
class TeacherAssignmentAdmin(admin.ModelAdmin):
    list_display = ("classroom", "teacher", "start_date", "end_date", "is_deleted")
    list_filter = ("is_deleted",)
