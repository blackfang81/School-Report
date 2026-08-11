"""Authentication and user management API views."""

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Role, User
from .permissions import IsEducationOfficer, IsStaffUser
from .serializers import (
    AdminCreateUserSerializer,
    ChangePasswordSerializer,
    ProfileUpdateSerializer,
    UserSerializer,
)


class CustomTokenObtainPairView(TokenObtainPairView):
    """Login with username and password; returns JWT access and refresh tokens."""


class MeView(generics.RetrieveUpdateAPIView):
    """Return or update the authenticated user's profile."""

    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return ProfileUpdateSerializer
        return UserSerializer

    def update(self, request, *args, **kwargs):
        serializer = ProfileUpdateSerializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(self.get_object()).data)


class ChangePasswordView(APIView):
    """Change the authenticated user's password."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password changed successfully."}, status=status.HTTP_200_OK)


class RoleCheckView(APIView):
    """Simple endpoint confirming login status and current role."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response(
            {
                "username": user.username,
                "role": user.role,
                "role_display": user.get_role_display(),
                "is_teacher": user.is_teacher,
                "is_education_officer": user.is_education_officer,
                "is_finance_officer": user.is_finance_officer,
                "is_staff": user.is_staff,
            }
        )


class TeacherListView(generics.ListAPIView):
    """List active teachers; education officers only."""

    permission_classes = [IsEducationOfficer]
    serializer_class = UserSerializer

    def get_queryset(self):
        return User.objects.filter(role=Role.TEACHER, is_active=True).order_by("username")


class AdminCreateUserView(generics.CreateAPIView):
    """
    Create a new user with a specific role.

    Accessible to Django staff users (admin) via API or Django admin panel.
    """

    permission_classes = [IsStaffUser]
    serializer_class = AdminCreateUserSerializer
    queryset = User.objects.all()
