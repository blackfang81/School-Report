from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsEducationOfficer, IsTeacher
from config.viewsets import SoftDeleteModelViewSetMixin
from reports.models import ReportStatus, SessionReport
from reports.serializers import (
    ReportRejectSerializer,
    SessionReportCreateSerializer,
    SessionReportSerializer,
    SessionReportUpdateSerializer,
    TeacherSessionRosterSerializer,
)
from reports.services import get_teacher_session_roster


class SessionReportViewSet(SoftDeleteModelViewSetMixin, viewsets.ModelViewSet):
    """
    CRUD for class session reports with soft delete.

    Teachers create and edit their own pending/rejected reports.
    Education officers approve, reject, or soft-delete any report.
    Teachers may soft-delete only their own pending reports.
    """

    filterset_fields = [
        "classroom",
        "teacher",
        "status",
        "classroom__school",
        "classroom__term",
    ]
    ordering_fields = ["session_date", "submitted_at", "session_number"]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update"):
            return [IsTeacher()]
        if self.action in ("approve", "reject"):
            return [IsEducationOfficer()]
        if self.action == "my_sessions":
            return [IsTeacher()]
        if self.action == "destroy":
            return [IsAuthenticated()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = SessionReport.objects.select_related(
            "classroom",
            "classroom__school",
            "classroom__term",
            "teacher",
            "class_session",
        )
        user = self.request.user
        params = self.request.query_params

        if user.is_teacher:
            qs = qs.filter(teacher=user)
        elif user.is_education_officer:
            if school := params.get("school"):
                qs = qs.filter(classroom__school_id=school)
            if classroom := params.get("classroom"):
                qs = qs.filter(classroom_id=classroom)
            if teacher := params.get("teacher"):
                qs = qs.filter(teacher_id=teacher)
            if term := params.get("term"):
                qs = qs.filter(classroom__term_id=term)
            if date_from := params.get("date_from"):
                qs = qs.filter(session_date__gte=date_from)
            if date_to := params.get("date_to"):
                qs = qs.filter(session_date__lte=date_to)
        elif user.is_finance_officer:
            qs = qs.none()
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return SessionReportCreateSerializer
        if self.action in ("update", "partial_update"):
            return SessionReportUpdateSerializer
        return SessionReportSerializer

    def create(self, request, *args, **kwargs):
        serializer = SessionReportCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        classroom = serializer.validated_data["classroom"]
        class_session = serializer.validated_data["class_session"]
        report = SessionReport.objects.create(
            classroom=classroom,
            class_session=class_session,
            teacher=request.user,
            session_date=class_session.session_date,
            session_number=class_session.session_number,
            summary=serializer.validated_data["summary"],
            present_count=serializer.validated_data["present_count"],
            absent_count=serializer.validated_data["absent_count"],
            status=ReportStatus.PENDING,
        )
        return Response(
            SessionReportSerializer(report).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = SessionReportUpdateSerializer(
            instance, data=request.data, partial=partial, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(instance, field, value)
        instance.status = ReportStatus.PENDING
        instance.officer_note = ""
        instance.approved_at = None
        instance.is_salary_eligible = False
        instance.save()
        return Response(SessionReportSerializer(instance).data)

    def destroy(self, request, *args, **kwargs):
        report = self.get_object()
        user = request.user

        if user.is_education_officer:
            return super().destroy(request, *args, **kwargs)

        if user.is_teacher and report.teacher_id == user.id and report.status == ReportStatus.PENDING:
            return super().destroy(request, *args, **kwargs)

        return Response(
            {"detail": "You cannot delete this report."},
            status=status.HTTP_403_FORBIDDEN,
        )

    @action(detail=False, methods=["get"], url_path="my-sessions")
    def my_sessions(self, request):
        """List all assigned class sessions for the teacher with report status."""
        roster = get_teacher_session_roster(request.user)
        serializer = TeacherSessionRosterSerializer(roster, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve a pending report; clears any previous rejection note."""
        report = self.get_object()
        report.officer_note = ""
        report.mark_approved()
        return Response(SessionReportSerializer(report).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """Reject a report; rejection reason is required."""
        report = self.get_object()
        serializer = ReportRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report.mark_rejected(serializer.validated_data["note"])
        return Response(SessionReportSerializer(report).data)
