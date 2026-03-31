"""Logger factory helpers."""

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a logger for the given module or class name."""
    return logging.getLogger(name)