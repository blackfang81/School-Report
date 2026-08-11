"""Custom DRF exception handling with structured error responses."""

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    Wrap DRF errors in a consistent ``error_code`` / ``error_message`` shape.

    Falls back to DRF's default handler for unrecognised exceptions.
    """
    response = exception_handler(exc, context)
    if response is None:
        return response

    if isinstance(exc, APIException):
        error_code = getattr(exc, "default_code", "error")
        if isinstance(exc.detail, dict):
            response.data = {
                "error_code": error_code,
                "error_message": exc.detail,
            }
        elif isinstance(exc.detail, list):
            response.data = {
                "error_code": error_code,
                "error_message": " ".join(str(item) for item in exc.detail),
            }
        else:
            response.data = {
                "error_code": error_code,
                "error_message": str(exc.detail),
            }
    return response


class ValidationErrorWithCode(APIException):
    """Validation error carrying an explicit machine-readable code."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "validation_error"

    def __init__(self, message, code="validation_error"):
        self.default_code = code
        super().__init__(detail=message, code=code)
