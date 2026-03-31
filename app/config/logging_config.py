"""Central logging configuration."""

import logging
import sys

from app.utils.logging_filter import MdcFilter


DEFAULT_LOG_FORMAT = (
    "%(asctime)s %(levelname)s "
    "[app_type=%(app_type)s] "
    "[class=%(class_name)s] "
    "[job_id=%(job_id)s] "
    "[request_id=%(request_id)s] "
    "%(message)s"
)

DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(app_type: str, log_level: str = "INFO") -> None:
    """Configure root logging once for the current process."""
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(_to_level(log_level))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(_to_level(log_level))
    handler.addFilter(MdcFilter())
    handler.setFormatter(logging.Formatter(DEFAULT_LOG_FORMAT, DEFAULT_DATE_FORMAT))

    root_logger.addHandler(handler)

    _set_default_app_type(app_type)
    _quiet_noisy_loggers()


def _to_level(log_level: str) -> int:
    """Convert a string log level into a logging constant."""
    return getattr(logging, (log_level or "INFO").upper(), logging.INFO)


def _set_default_app_type(app_type: str) -> None:
    """Attach the process app type to every emitted record."""
    original_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = original_factory(*args, **kwargs)
        record.app_type = app_type
        return record

    logging.setLogRecordFactory(record_factory)


def _quiet_noisy_loggers() -> None:
    """Reduce noise from very chatty libraries."""
    logging.getLogger("werkzeug").setLevel(logging.INFO)
    logging.getLogger("rq.worker").setLevel(logging.INFO)
    logging.getLogger("urllib3").setLevel(logging.WARNING)