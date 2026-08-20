"""API viewsets for education resources."""

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsEducationOfficer
from config.viewsets import SoftDeleteModelViewSetMixin
from education.filters import ClassRoomFilter, TeacherAssignmentFilter, TermFilter
from education.models import ClassRoom, ClassSession, School, TeacherAssignment, Term
from education.serializers import (
    ClassRoomSerializer,
    ClassSessionSerializer,
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
    filterset_class = TermFilter
    search_fields = ["name"]
    ordering_fields = ["start_date", "name", "end_date"]

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
            "assignments__teacher", "weekdays", "sessions"
        )
        user = self.request.user
        if user.is_teacher:
            return qs.filter(assignments__teacher=user).distinct()
        return qs

    @action(detail=True, methods=["get"])
    def sessions(self, request, pk=None):
        """List scheduled sessions for a class, optionally hiding sessions with reports."""
        classroom = self.get_object()
        qs = classroom.sessions.filter(is_deleted=False).order_by("session_number")
        if request.query_params.get("available") == "true":
            reported_ids = classroom.reports.filter(is_deleted=False).values_list(
                "class_session_id", flat=True
            )
            qs = qs.exclude(id__in=reported_ids)
        serializer = ClassSessionSerializer(qs, many=True)
        return Response(serializer.data)


class ClassSessionViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to scheduled class sessions."""

    serializer_class = ClassSessionSerializer
    filterset_fields = ["classroom"]
    ordering_fields = ["session_number", "session_date"]

    def get_queryset(self):
        qs = ClassSession.objects.select_related("classroom", "classroom__school")
        user = self.request.user
        if user.is_teacher:
            qs = qs.filter(classroom__assignments__teacher=user).distinct()
        if self.request.query_params.get("available") == "true":
            qs = qs.exclude(reports__is_deleted=False)
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
