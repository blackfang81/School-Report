"""Shared API views for project utilities."""

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsEducationOfficer
from config.project_clock import (
    get_override,
    is_clock_override_enabled,
    project_now,
    set_override,
)
from config.project_clock import parse_override_value


class ProjectClockView(APIView):
    """
    Get or set the project's virtual clock.

    Enabled when ``PROJECT_CLOCK_ENABLED`` is true (defaults to ``DEBUG``).
    Education officers can simulate "now" for testing approval deadlines and timelines.
    """

    permission_classes = [IsEducationOfficer]

    def get(self, request):
        if not is_clock_override_enabled():
            return Response(
                {"detail": "Project clock override is disabled."},
                status=status.HTTP_403_FORBIDDEN,
            )
        override = get_override()
        now = project_now()
        return Response(
            {
                "enabled": True,
                "is_overridden": override is not None,
                "override": override.isoformat() if override else None,
                "project_now": now.isoformat(),
                "real_now": timezone.now().isoformat(),
            }
        )

    def post(self, request):
        if not is_clock_override_enabled():
            return Response(
                {"detail": "Project clock override is disabled."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if request.data.get("reset"):
            set_override(None)
        else:
            raw = request.data.get("datetime") or request.data.get("now")
            if not raw:
                return Response(
                    {"error_message": "Provide 'datetime' (ISO format) or set reset=true."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                set_override(parse_override_value(raw))
            except ValueError as exc:
                return Response({"error_message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        override = get_override()
        now = project_now()
        return Response(
            {
                "enabled": True,
                "is_overridden": override is not None,
                "override": override.isoformat() if override else None,
                "project_now": now.isoformat(),
                "real_now": timezone.now().isoformat(),
            }
        )
