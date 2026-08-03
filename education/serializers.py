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
