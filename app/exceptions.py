"""Application-specific exceptions and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from typing import Any


@dataclass(slots=True)
class ErrorPayload:
    """Serializable error response payload."""

    error: str
    code: str
    status_code: int
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the payload to a JSON-safe dictionary."""
        payload = {
            "error": self.error,
            "code": self.code,
            "status_code": self.status_code,
        }
        if self.details:
            payload["details"] = self.details
        return payload


class AppError(Exception):
    """Base application exception with a structured payload."""

    status_code = HTTPStatus.BAD_REQUEST
    code = "app_error"
    message = "The request could not be processed."

    def __init__(self, message: str | None = None, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = details or {}

    def to_payload(self) -> ErrorPayload:
        """Build the structured error payload."""
        return ErrorPayload(
            error=self.message,
            code=self.code,
            status_code=int(self.status_code),
            details=self.details or None,
        )


class BadRequestError(AppError):
    """Raised when the client sent an invalid request."""

    status_code = HTTPStatus.BAD_REQUEST
    code = "bad_request"
    message = "The request payload was invalid."


class InvalidJsonError(BadRequestError):
    """Raised when JSON parsing fails."""

    code = "invalid_json"
    message = "Request body must be valid JSON."


class MissingFieldError(BadRequestError):
    """Raised when a required field is missing."""

    code = "missing_field"

    def __init__(self, field_name: str) -> None:
        super().__init__(
            f"{field_name} is required",
            details={"field": field_name},
        )


class InvalidFieldError(BadRequestError):
    """Raised when a field cannot be parsed or validated."""

    code = "invalid_field"

    def __init__(self, field_name: str, reason: str) -> None:
        super().__init__(
            f"{field_name} is invalid: {reason}",
            details={"field": field_name, "reason": reason},
        )


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    status_code = HTTPStatus.NOT_FOUND
    code = "not_found"
    message = "The requested resource was not found."


class ControllerRenderError(AppError):
    """Raised by UI controllers so templates can render a friendly error card."""

    status_code = HTTPStatus.BAD_REQUEST
    code = "controller_render_error"
    message = "Unable to process the request."


class YoutubeDownloadError(AppError):
    """Raised when yt-dlp fails to download media."""

    status_code = HTTPStatus.BAD_REQUEST
    code = "youtube_download_error"
    message = "Failed to download media from YouTube."