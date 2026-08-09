from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsEducationOfficer, IsTeacher
from reports.models import ReportStatus, SessionReport
from reports.serializers import (
    ReportReviewSerializer,
    SessionReportCreateSerializer,
    SessionReportSerializer,
    SessionReportUpdateSerializer,
)


class SessionReportViewSet(viewsets.ModelViewSet):
    filterset_fields = ["classroom", "teacher", "status", "classroom__school"]
    ordering_fields = ["session_date", "submitted_at", "session_number"]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update"):
            return [IsTeacher()]
        if self.action in ("approve", "reject"):
            return [IsEducationOfficer()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = SessionReport.objects.select_related(
            "classroom", "classroom__school", "teacher"
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
        report = SessionReport.objects.create(
            classroom=classroom,
            teacher=request.user,
            session_date=serializer.validated_data["session_date"],
            session_number=SessionReport.next_session_number(classroom),
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
        return Response(
            {"detail": "Deleting reports is not allowed."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        report = self.get_object()
        serializer = ReportReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report.officer_note = serializer.validated_data.get("note", "")
        report.mark_approved()
        return Response(SessionReportSerializer(report).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        report = self.get_object()
        serializer = ReportReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report.mark_rejected(serializer.validated_data.get("note", ""))
        return Response(SessionReportSerializer(report).data)
