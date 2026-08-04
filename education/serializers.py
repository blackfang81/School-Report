from rest_framework import serializers

from education.models import ClassRoom, School, TeacherAssignment, Term


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = (
            "id",
            "name",
            "level",
            "gender",
            "email",
            "phone",
            "fax",
            "address",
        )


class TermSerializer(serializers.ModelSerializer):
    class Meta:
        model = Term
        fields = ("id", "name", "start_date", "end_date", "is_summer")

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError("End date cannot be before start date.")

        instance = self.instance or Term(
            **{k: v for k, v in attrs.items() if k in ("start_date", "end_date", "name", "is_summer")}
        )
        if self.instance:
            for key, value in attrs.items():
                setattr(instance, key, value)
        try:
            instance.full_clean()
        except Exception as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc)) from exc
        return attrs


class ClassRoomSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source="school.name", read_only=True)
    term_name = serializers.CharField(source="term.name", read_only=True)
    session_duration_display = serializers.CharField(
        source="get_session_duration_display", read_only=True
    )

    class Meta:
        model = ClassRoom
        fields = (
            "id",
            "school",
            "school_name",
            "term",
            "term_name",
            "name",
            "class_type",
            "session_duration",
            "session_duration_display",
            "start_date",
            "end_date",
        )

    def validate_session_duration(self, value):
        if value not in (60, 90, 120):
            raise serializers.ValidationError("Session duration must be 60, 90, or 120 minutes.")
        return value

