from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.views import (
    ChangePasswordView,
    CustomTokenObtainPairView,
    MeView,
    RoleCheckView,
    TeacherListView,
)
from education.views import ClassRoomViewSet, SchoolViewSet, TeacherAssignmentViewSet, TermViewSet

router = DefaultRouter()
router.register("schools", SchoolViewSet, basename="school")
router.register("terms", TermViewSet, basename="term")
router.register("classes", ClassRoomViewSet, basename="class")
router.register("teacher-assignments", TeacherAssignmentViewSet, basename="teacher-assignment")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/me/", MeView.as_view(), name="me"),
    path("api/auth/change-password/", ChangePasswordView.as_view(), name="change_password"),
    path("api/auth/role/", RoleCheckView.as_view(), name="role_check"),
    path("api/auth/teachers/", TeacherListView.as_view(), name="teacher_list"),
    path("api/", include(router.urls)),
]
