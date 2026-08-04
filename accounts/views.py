from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import Role, User
from .permissions import IsEducationOfficer
from .serializers import ChangePasswordSerializer, ProfileUpdateSerializer, UserSerializer


class CustomTokenObtainPairView(TokenObtainPairView):
    """Login with username and password; returns JWT tokens."""


class MeView(generics.RetrieveUpdateAPIView):
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
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password changed successfully."}, status=status.HTTP_200_OK)


class RoleCheckView(APIView):
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
            }
        )


class TeacherListView(generics.ListAPIView):
    permission_classes = [IsEducationOfficer]
    serializer_class = UserSerializer

    def get_queryset(self):
        return User.objects.filter(role=Role.TEACHER, is_active=True).order_by("username")
