"""Filter sets for education API list endpoints."""

import django_filters

from education.models import ClassRoom, TeacherAssignment


class ClassRoomFilter(django_filters.FilterSet):
    """Filter classes by school, term, teacher, and other attributes."""

    teacher = django_filters.NumberFilter(field_name="assignments__teacher", distinct=True)

    class Meta:
        model = ClassRoom
        fields = ["school", "term", "class_type", "session_duration", "teacher"]


class TeacherAssignmentFilter(django_filters.FilterSet):
    """Filter teacher-class assignments."""

    school = django_filters.NumberFilter(field_name="classroom__school")
    term = django_filters.NumberFilter(field_name="classroom__term")

    class Meta:
        model = TeacherAssignment
        fields = ["classroom", "teacher", "school", "term"]
