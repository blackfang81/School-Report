from rest_framework import serializers

from config.project_clock import project_localdate
from reports.models import ReportStatus, SessionReport


class SessionReportSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    classroom_name = serializers.CharField(source="classroom.name", read_only=True)
    teacher_name = serializers.CharField(source="teacher.get_full_name", read_only=True)
    school_name = serializers.CharField(source="classroom.school.name", read_only=True)
    term_name = serializers.CharField(source="classroom.term.name", read_only=True)

    class Meta:
        model = SessionReport
        fields = (
            "id",
            "classroom",
            "classroom_name",
            "school_name",
            "term_name",
            "class_session",
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
            "is_deleted",
            "deleted_at",
        )
        read_only_fields = (
            "id",
            "teacher",
            "session_date",
            "session_number",
            "status",
            "status_display",
            "officer_note",
            "submitted_at",
            "approved_at",
            "is_salary_eligible",
            "is_deleted",
            "deleted_at",
            "teacher_name",
            "classroom_name",
            "school_name",
            "term_name",
        )


class SessionReportCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionReport
        fields = (
            "classroom",
            "class_session",
            "summary",
            "present_count",
            "absent_count",
        )

    def validate(self, attrs):
        request = self.context["request"]
        teacher = request.user
        classroom = attrs["classroom"]
        class_session = attrs["class_session"]

        if class_session.classroom_id != classroom.id:
            raise serializers.ValidationError(
                {"class_session": "Selected session does not belong to this class."}
            )

        try:
            SessionReport.validate_class_session_for_teacher(teacher, class_session)
        except ValueError as exc:
            raise serializers.ValidationError({"class_session": str(exc)}) from exc

        if class_session.session_date > project_localdate():
            raise serializers.ValidationError(
                {"class_session": "You can submit a report only after the session date."}
            )

        if attrs["present_count"] + attrs["absent_count"] == 0:
            raise serializers.ValidationError("Present and absent counts must add up to more than zero.")

        return attrs


class SessionReportUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionReport
        fields = (
            "summary",
            "present_count",
            "absent_count",
        )

    def validate(self, attrs):
        instance = self.instance
        if instance.status == ReportStatus.APPROVED:
            raise serializers.ValidationError("Approved reports cannot be edited.")

        present = attrs.get("present_count", instance.present_count)
        absent = attrs.get("absent_count", instance.absent_count)
        if present + absent == 0:
            raise serializers.ValidationError("Present and absent counts must add up to more than zero.")

        return attrs


class ReportRejectSerializer(serializers.Serializer):
    note = serializers.CharField(required=True, allow_blank=False)

    def validate_note(self, value):
        if not value.strip():
            raise serializers.ValidationError("Rejection reason is required.")
        return value.strip()


class TeacherSessionRosterSerializer(serializers.Serializer):
    class_session_id = serializers.IntegerField()
    classroom_id = serializers.IntegerField()
    classroom_name = serializers.CharField()
    school_name = serializers.CharField()
    term_name = serializers.CharField()
    session_number = serializers.IntegerField()
    session_date = serializers.DateField()
    weekday = serializers.CharField()
    session_duration = serializers.IntegerField()
    session_status = serializers.CharField()
    can_submit = serializers.BooleanField()
    can_edit = serializers.BooleanField()
    report_id = serializers.IntegerField(allow_null=True)
    report_status = serializers.CharField(allow_null=True)
    is_salary_eligible = serializers.BooleanField(allow_null=True)
    officer_note = serializers.CharField(allow_blank=True)
