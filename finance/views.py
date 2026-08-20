from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsFinanceOfficer, IsTeacher
from config.datetime_utils import calendar_month_range, payroll_period_for_calculation_date
from config.viewsets import SoftDeleteModelViewSetMixin
from finance.models import SalaryRecord, TermBaseRate
from finance.services import calculate_monthly_salaries, calculate_salaries_for_period


class TermBaseRateSerializer(serializers.ModelSerializer):
    term_name = serializers.CharField(source="term.name", read_only=True)

    class Meta:
        model = TermBaseRate
        fields = ("id", "term", "term_name", "base_rate", "is_deleted", "deleted_at")
        read_only_fields = ("is_deleted", "deleted_at")


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
            "calculation_date",
            "period_start",
            "period_end",
            "calculated_at",
        )
        read_only_fields = fields


class CalculateSalarySerializer(serializers.Serializer):
    calculation_date = serializers.DateField(required=False)
    year = serializers.IntegerField(min_value=2000, max_value=2100, required=False)
    month = serializers.IntegerField(min_value=1, max_value=12, required=False)

    def validate(self, attrs):
        calculation_date = attrs.get("calculation_date")
        year = attrs.get("year")
        month = attrs.get("month")

        if calculation_date is not None:
            period_start, period_end = payroll_period_for_calculation_date(calculation_date)
            attrs["period_start"] = period_start
            attrs["period_end"] = period_end
            return attrs

        if year is not None and month is not None:
            period_start, period_end = calendar_month_range(year, month)
            attrs["period_start"] = period_start
            attrs["period_end"] = period_end
            attrs["payroll_year"] = year
            attrs["payroll_month"] = month
            return attrs

        raise serializers.ValidationError(
            "Provide either calculation_date or both year and month."
        )


class TermBaseRateViewSet(SoftDeleteModelViewSetMixin, viewsets.ModelViewSet):
    """
    CRUD for per-term base salary rates.

    Finance officers manage rates; DELETE performs a soft delete.
    """

    queryset = TermBaseRate.objects.select_related("term").order_by("id")
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
        qs = SalaryRecord.objects.filter(teacher=request.user).order_by(
            "-calculation_date", "-year", "-month"
        )
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
        calculation_date = serializer.validated_data.get("calculation_date")
        period_start = serializer.validated_data["period_start"]
        period_end = serializer.validated_data["period_end"]

        if calculation_date is not None:
            records, skipped = calculate_salaries_for_period(
                period_start,
                period_end,
                calculation_date=calculation_date,
            )
            detail = (
                f"Calculation date {calculation_date}: payroll period "
                f"{period_start} to {period_end}. {len(records)} teacher(s) paid."
            )
            payroll_year = period_end.year
            payroll_month = period_end.month
        else:
            payroll_year = serializer.validated_data["payroll_year"]
            payroll_month = serializer.validated_data["payroll_month"]
            records, skipped = calculate_monthly_salaries(payroll_year, payroll_month)
            detail = (
                f"Calculated salary for {len(records)} teacher(s) "
                f"for {payroll_year}-{payroll_month:02d}."
            )

        return Response(
            {
                "detail": detail,
                "payroll_year": payroll_year,
                "payroll_month": payroll_month,
                "period_start": period_start,
                "period_end": period_end,
                "calculation_date": calculation_date,
                "records": SalaryRecordSerializer(records, many=True).data,
                "skipped": skipped,
            },
            status=status.HTTP_200_OK,
        )
