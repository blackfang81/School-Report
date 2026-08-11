"""API viewsets for education resources."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsEducationOfficer
from config.viewsets import SoftDeleteModelViewSetMixin
from education.filters import ClassRoomFilter, TeacherAssignmentFilter
from education.models import ClassRoom, School, TeacherAssignment, Term
from education.serializers import (
    ClassRoomSerializer,
    SchoolSerializer,
    TeacherAssignmentSerializer,
    TermSerializer,
)


class SchoolViewSet(SoftDeleteModelViewSetMixin, viewsets.ModelViewSet):
    """
    CRUD for schools.

    Education officers can create/update/delete; all authenticated users can list/retrieve.
    """

    queryset = School.objects.all()
    serializer_class = SchoolSerializer
    filterset_fields = ["name", "level", "gender"]
    search_fields = ["name"]
    ordering_fields = ["name"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsEducationOfficer()]


class TermViewSet(SoftDeleteModelViewSetMixin, viewsets.ModelViewSet):
    """
    CRUD for academic terms.

    Validates non-overlapping date ranges on create/update.
    """

    queryset = Term.objects.all()
    serializer_class = TermSerializer
    filterset_fields = ["is_summer", "name"]
    ordering_fields = ["start_date", "name"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsEducationOfficer()]


class ClassRoomViewSet(SoftDeleteModelViewSetMixin, viewsets.ModelViewSet):
    """
    CRUD for classes.

    Teachers only see classes they are (or were) assigned to.
    """

    serializer_class = ClassRoomSerializer
    filterset_class = ClassRoomFilter
    search_fields = ["name"]
    ordering_fields = ["start_date", "name"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsEducationOfficer()]

    def get_queryset(self):
        qs = ClassRoom.objects.select_related("school", "term").prefetch_related(
            "assignments__teacher"
        )
        user = self.request.user
        if user.is_teacher:
            return qs.filter(assignments__teacher=user).distinct()
        return qs


class TeacherAssignmentViewSet(SoftDeleteModelViewSetMixin, viewsets.ModelViewSet):
    """
    CRUD for teacher-class assignments.

    Supports sequential multi-teacher assignments without date overlap.
    """

    serializer_class = TeacherAssignmentSerializer
    filterset_class = TeacherAssignmentFilter
    ordering_fields = ["start_date"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsEducationOfficer()]

    def get_queryset(self):
        qs = TeacherAssignment.objects.select_related("teacher", "classroom", "classroom__school")
        user = self.request.user
        if user.is_teacher:
            return qs.filter(teacher=user)
        return qs
