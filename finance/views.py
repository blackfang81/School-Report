from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsFinanceOfficer, IsTeacher
from finance.models import SalaryRecord, TermBaseRate
from finance.services import calculate_monthly_salaries


class TermBaseRateSerializer(serializers.ModelSerializer):
    term_name = serializers.CharField(source="term.name", read_only=True)

    class Meta:
        model = TermBaseRate
        fields = ("id", "term", "term_name", "base_rate")


class SalaryRecordSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.get_full_name", read_only=True)

    class Meta:
        model = SalaryRecord
        fields = (
            "id",
            "teacher",
            "teacher_name",
            "year",
            "month",
            "amount",
            "calculated_at",
        )
        read_only_fields = fields


class CalculateSalarySerializer(serializers.Serializer):
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    month = serializers.IntegerField(min_value=1, max_value=12)


class TermBaseRateViewSet(viewsets.ModelViewSet):
    queryset = TermBaseRate.objects.select_related("term")
    serializer_class = TermBaseRateSerializer
    permission_classes = [IsFinanceOfficer]


class SalaryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SalaryRecordSerializer
    filterset_fields = ["year", "month", "teacher"]
    ordering_fields = ["year", "month", "amount"]

    def get_permissions(self):
        if self.action == "my_salaries":
            return [IsTeacher()]
        return [IsFinanceOfficer()]

    def get_queryset(self):
        return SalaryRecord.objects.select_related("teacher")

    @action(detail=False, methods=["get"], url_path="my")
    def my_salaries(self, request):
        qs = SalaryRecord.objects.filter(teacher=request.user).order_by("-year", "-month")
        page = self.paginate_queryset(qs)
        serializer = SalaryRecordSerializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class CalculateSalariesView(APIView):
    permission_classes = [IsFinanceOfficer]

    def post(self, request):
        serializer = CalculateSalarySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        year = serializer.validated_data["year"]
        month = serializer.validated_data["month"]
        records = calculate_monthly_salaries(year, month)
        return Response(
            {
                "detail": f"Calculated salary for {len(records)} teacher(s).",
                "records": SalaryRecordSerializer(records, many=True).data,
            },
            status=status.HTTP_200_OK,
        )
