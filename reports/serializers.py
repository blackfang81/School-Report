from rest_framework import serializers

from reports.models import ReportStatus, SessionReport


class SessionReportSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    classroom_name = serializers.CharField(source="classroom.name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.get_full_name", read_only=True)
    school_name = serializers.CharField(source="classroom.school.name", read_only=True)

    class Meta:
        model = SessionReport
        fields = (
            "id",
            "classroom",
            "classroom_name",
            "school_name",
            "teacher",
            "teacher_name",
            "session_date",
            "session_number",
            "summary",
            "present_count",
            "absent_count",
            "status",
            "status_display",
            "officer_note",
            "submitted_at",
            "approved_at",
            "is_salary_eligible",
        )
        read_only_fields = (
            "id",
            "teacher",
            "session_number",
            "status",
            "status_display",
            "officer_note",
            "submitted_at",
            "approved_at",
            "is_salary_eligible",
            "teacher_name",
            "classroom_name",
            "school_name",
        )


class SessionReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionReport
        fields = (
            "classroom",
            "session_date",
            "summary",
            "present_count",
            "absent_count",
        )

    def validate(self, attrs):
        request = self.context["request"]
        teacher = request.user
        classroom = attrs["classroom"]
        session_date = attrs["session_date"]

        if not SessionReport.teacher_owns_class_on_date(teacher, classroom, session_date):
            raise serializers.ValidationError("You are not assigned to this class on the selected date.")

        if attrs["present_count"] + attrs["absent_count"] == 0:
            raise serializers.ValidationError("Present and absent counts must add up to more than zero.")

        return attrs

