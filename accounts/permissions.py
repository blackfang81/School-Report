"""Role-based permission classes for DRF views."""

from rest_framework import permissions


class IsTeacher(permissions.BasePermission):
    """Allow access only to authenticated teachers."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_teacher


class IsEducationOfficer(permissions.BasePermission):
    """Allow access only to authenticated education officers."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_education_officer


class IsFinanceOfficer(permissions.BasePermission):
    """Allow access only to authenticated finance officers."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_finance_officer


class IsStaffUser(permissions.BasePermission):
    """
    Allow access to Django staff users.

    Used for admin-only endpoints such as user creation via API.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff
