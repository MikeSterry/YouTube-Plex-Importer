"""Logging filters."""

import logging

from app.utils.logging_context import get_job_id, get_request_id


class MdcFilter(logging.Filter):
    """Inject MDC-style values into each log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Attach contextual fields used by the log formatter."""
        record.job_id = get_job_id()
        record.request_id = get_request_id()
        record.app_type = getattr(record, "app_type", "app")
        record.class_name = record.name
        return True