"""Serializers for user accounts and authentication."""

from rest_framework import serializers

from .models import Role, User


class UserSerializer(serializers.ModelSerializer):
    """Public user profile fields exposed through the API."""

    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "role",
            "role_display",
            "phone",
            "emergency_phone",
            "is_staff",
        )
        read_only_fields = ("id", "username", "role", "role_display", "is_staff")


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Fields a user may update on their own profile."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone", "emergency_phone")


class ChangePasswordSerializer(serializers.Serializer):
    """Validate and apply a password change for the current user."""

    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user


class AdminCreateUserSerializer(serializers.ModelSerializer):
    """Serializer used by staff to create new users with a role."""

    password = serializers.CharField(write_only=True, min_length=8)
    is_staff = serializers.BooleanField(default=False, required=False)

    class Meta:
        model = User
        fields = (
            "username",
            "password",
            "role",
            "first_name",
            "last_name",
            "phone",
            "emergency_phone",
            "is_staff",
        )

    def validate_role(self, value):
        if value not in Role.values:
            raise serializers.ValidationError("Invalid role.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user
