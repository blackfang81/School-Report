"""Shared DRF viewset base classes."""

from rest_framework import status
from rest_framework.response import Response


class SoftDeleteModelViewSetMixin:
    """
    Mixin for ModelViewSets that performs soft delete on destroy.

    Sets ``is_deleted=True`` and ``deleted_at`` instead of removing the row.
    """

    def perform_destroy(self, instance):
        """Soft-delete the given instance."""
        instance.delete()

    def destroy(self, request, *args, **kwargs):
        """Return 204 after soft-deleting the target object."""
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
