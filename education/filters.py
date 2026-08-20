"""Filter sets for education API list endpoints."""

import django_filters

from education.models import ClassRoom, TeacherAssignment, Term


class TermFilter(django_filters.FilterSet):
    """Filter terms by name, summer flag, and date range."""

    start_date_from = django_filters.DateFilter(field_name="start_date", lookup_expr="gte")
    start_date_to = django_filters.DateFilter(field_name="start_date", lookup_expr="lte")
    end_date_from = django_filters.DateFilter(field_name="end_date", lookup_expr="gte")
    end_date_to = django_filters.DateFilter(field_name="end_date", lookup_expr="lte")

    class Meta:
        model = Term
        fields = ["is_summer", "name"]


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
