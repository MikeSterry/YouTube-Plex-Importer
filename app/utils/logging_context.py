"""Logging context helpers."""

from contextvars import ContextVar


_job_id_var: ContextVar[str] = ContextVar("job_id", default="-")
_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def set_job_id(job_id: str | None) -> None:
    """Store the active job identifier for logging."""
    _job_id_var.set(job_id or "-")


def get_job_id() -> str:
    """Return the active job identifier for logging."""
    return _job_id_var.get()


def clear_job_id() -> None:
    """Clear the active job identifier for logging."""
    _job_id_var.set("-")


def set_request_id(request_id: str | None) -> None:
    """Store the active request identifier for logging."""
    _request_id_var.set(request_id or "-")


def get_request_id() -> str:
    """Return the active request identifier for logging."""
    return _request_id_var.get()


def clear_request_id() -> None:
    """Clear the active request identifier for logging."""
    _request_id_var.set("-")