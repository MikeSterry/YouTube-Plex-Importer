"""File and name utilities."""

import re
from pathlib import Path


class FileNameUtils:
    """Helpers for safe file and folder names."""

    @staticmethod
    def slugify(value: str) -> str:
        """Convert arbitrary text to a filesystem-friendly slug."""
        cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip())
        cleaned = re.sub(r"-+", "-", cleaned).strip("-._")
        return cleaned or "output"

    @staticmethod
    def sanitize_display_name(value: str) -> str:
        """Convert arbitrary text to a readable filesystem-safe name that can keep spaces."""
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", value.strip())
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
        return cleaned or "output"

    @staticmethod
    def extension(path_or_url: str) -> str:
        """Extract a lowercase suffix from a path-like value."""
        return Path(path_or_url.split("?")[0]).suffix.lower()