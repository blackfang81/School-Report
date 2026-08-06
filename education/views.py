from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsEducationOfficer, IsTeacher
from .models import ClassRoom, School, TeacherAssignment, Term
from .serializers import (
    ClassRoomSerializer,
    SchoolSerializer,
    TeacherAssignmentSerializer,
    TermSerializer,
)


class SchoolViewSet(viewsets.ModelViewSet):
    queryset = School.objects.all()
    serializer_class = SchoolSerializer
    filterset_fields = ["name", "level", "gender"]
    search_fields = ["name"]
    ordering_fields = ["name"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsEducationOfficer()]


class TermViewSet(viewsets.ModelViewSet):
    queryset = Term.objects.all()
    serializer_class = TermSerializer
    filterset_fields = ["is_summer", "name"]
    ordering_fields = ["start_date", "name"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsEducationOfficer()]

    def perform_create(self, serializer):
        term = serializer.save()
        term.full_clean()
        term.save()

    def perform_update(self, serializer):
        term = serializer.save()
        term.full_clean()
        term.save()

