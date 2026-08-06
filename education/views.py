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
