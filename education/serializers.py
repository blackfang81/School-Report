"""Serializers for education API resources."""

from django.core.exceptions import ValidationError as DjangoValidationError
from config.project_clock import project_localdate
from education.session_helpers import ensure_classroom_sessions
from rest_framework import serializers

from education.models import ClassRoom, ClassSession, School, TeacherAssignment, Term, Weekday


def _raise_validation_error(exc):
    """Convert Django ValidationError into DRF ValidationError."""
    if hasattr(exc, "message_dict"):
        raise serializers.ValidationError(exc.message_dict) from exc
    if hasattr(exc, "messages"):
        raise serializers.ValidationError(exc.messages) from exc
    raise serializers.ValidationError(str(exc)) from exc


class SchoolSerializer(serializers.ModelSerializer):
    """Read/write serializer for ``School``."""

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
            "is_deleted",
            "deleted_at",
        )
        read_only_fields = ("is_deleted", "deleted_at")

    def validate(self, attrs):
        instance = self.instance or School()
        for key, value in attrs.items():
            setattr(instance, key, value)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            _raise_validation_error(exc)
        return attrs


class TermSerializer(serializers.ModelSerializer):
    """Read/write serializer for ``Term`` with overlap validation."""

    class Meta:
        model = Term
        fields = ("id", "name", "start_date", "end_date", "is_summer", "is_deleted", "deleted_at")
        read_only_fields = ("is_deleted", "deleted_at")

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "End date cannot be before start date."})

        instance = self.instance or Term()
        for key, value in attrs.items():
            setattr(instance, key, value)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            _raise_validation_error(exc)
        return attrs


class CurrentTeacherSerializer(serializers.Serializer):
    """Summary of the teacher currently assigned to a class."""

    assignment_id = serializers.IntegerField()
    teacher_id = serializers.IntegerField()
    teacher_name = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField(allow_null=True)


class ClassRoomSerializer(serializers.ModelSerializer):
    """Read/write serializer for ``ClassRoom`` including current teacher summary."""

    school_name = serializers.CharField(source="school.name", read_only=True)
    term_name = serializers.CharField(source="term.name", read_only=True)
    session_duration_display = serializers.CharField(
        source="get_session_duration_display", read_only=True
    )
    current_teacher = serializers.SerializerMethodField()
    weekdays = serializers.ListField(
        child=serializers.ChoiceField(choices=Weekday.choices),
        required=False,
        allow_empty=False,
        write_only=True,
    )
    weekday_list = serializers.SerializerMethodField(read_only=True)
    expected_session_count = serializers.SerializerMethodField(read_only=True)

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
            "weekdays",
            "weekday_list",
            "expected_session_count",
            "current_teacher",
            "is_deleted",
            "deleted_at",
        )
        read_only_fields = ("is_deleted", "deleted_at")

    def get_weekday_list(self, obj):
        return obj.get_weekdays()

    def get_expected_session_count(self, obj):
        return obj.sessions.filter(is_deleted=False).count()

    def get_current_teacher(self, obj):
        """Return the most relevant teacher assignment (active, upcoming, or last)."""
        assignment = obj.get_current_assignment(project_localdate())
        if not assignment:
            return None
        return {
            "assignment_id": assignment.id,
            "teacher_id": assignment.teacher_id,
            "teacher_name": assignment.teacher.get_full_name() or assignment.teacher.username,
            "start_date": assignment.start_date,
            "end_date": assignment.end_date,
        }

    def validate_session_duration(self, value):
        if value not in (60, 90, 120):
            raise serializers.ValidationError("Session duration must be 60, 90, or 120 minutes.")
        return value

    def validate(self, attrs):
        instance = self.instance or ClassRoom()
        for key, value in attrs.items():
            if key == "weekdays":
                continue
            setattr(instance, key, value)
        if "school" in attrs:
            instance.school = attrs["school"]
        if "term" in attrs:
            instance.term = attrs["term"]
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            _raise_validation_error(exc)

        weekdays = attrs.get("weekdays")
        if weekdays is not None and len(set(weekdays)) != len(weekdays):
            raise serializers.ValidationError({"weekdays": "Duplicate weekdays are not allowed."})

        if self.instance is None and weekdays is None:
            raise serializers.ValidationError(
                {"weekdays": "At least one weekly session day is required."}
            )

        return attrs

    def create(self, validated_data):
        weekdays = validated_data.pop("weekdays")
        classroom = ClassRoom.objects.create(**validated_data)
        self._save_weekdays(classroom, weekdays)
        classroom.regenerate_sessions()
        return classroom

    def update(self, instance, validated_data):
        weekdays = validated_data.pop("weekdays", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.save()
        if weekdays is not None:
            self._save_weekdays(instance, weekdays)
            instance.regenerate_sessions()
        return instance

    def _save_weekdays(self, classroom, weekdays):
        from education.models import ClassRoomWeekday

        unique_weekdays = sorted(set(weekdays))
        existing = {
            item.weekday: item
            for item in ClassRoomWeekday.all_objects.filter(classroom=classroom)
        }
        for weekday in unique_weekdays:
            item = existing.get(weekday)
            if item and item.is_deleted:
                item.restore()
            elif not item:
                ClassRoomWeekday.objects.create(classroom=classroom, weekday=weekday)

        for weekday, item in existing.items():
            if weekday not in unique_weekdays and not item.is_deleted:
                item.delete()


class ClassSessionSerializer(serializers.ModelSerializer):
    """Read-only serializer for scheduled class sessions."""

    has_report = serializers.BooleanField(read_only=True)

    class Meta:
        model = ClassSession
        fields = (
            "id",
            "classroom",
            "session_number",
            "session_date",
            "has_report",
            "is_deleted",
            "deleted_at",
        )
        read_only_fields = fields


class TeacherAssignmentSerializer(serializers.ModelSerializer):
    """Read/write serializer for ``TeacherAssignment`` with overlap validation."""

    teacher_name = serializers.CharField(source="teacher.get_full_name", read_only=True)
    classroom_name = serializers.CharField(source="classroom.name", read_only=True)

    class Meta:
        model = TeacherAssignment
        fields = (
            "id",
            "classroom",
            "classroom_name",
            "teacher",
            "teacher_name",
            "start_date",
            "end_date",
            "is_deleted",
            "deleted_at",
        )
        read_only_fields = ("is_deleted", "deleted_at")

    def create(self, validated_data):
        assignment = super().create(validated_data)
        ensure_classroom_sessions(assignment.classroom)
        return assignment

    def update(self, instance, validated_data):
        assignment = super().update(instance, validated_data)
        ensure_classroom_sessions(assignment.classroom)
        return assignment

    def validate_teacher(self, value):
        if not value.is_teacher:
            raise serializers.ValidationError("Only users with the teacher role can be assigned.")
        return value

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "End date cannot be before start date."})

        classroom = attrs.get("classroom", getattr(self.instance, "classroom", None))
        teacher = attrs.get("teacher", getattr(self.instance, "teacher", None))

        instance = self.instance or TeacherAssignment()
        for key, value in attrs.items():
            setattr(instance, key, value)
        if classroom is not None:
            instance.classroom = classroom
        if teacher is not None:
            instance.teacher = teacher

        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            _raise_validation_error(exc)
        return attrs
