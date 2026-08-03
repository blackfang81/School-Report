from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "first_name", "last_name", "role", "phone", "is_active")
    list_filter = ("role", "is_active")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Extra", {"fields": ("role", "phone", "emergency_phone")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Extra", {"fields": ("role", "phone", "emergency_phone")}),
    )
