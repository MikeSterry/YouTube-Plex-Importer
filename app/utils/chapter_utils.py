"""Chapter parsing helpers."""

import re


class ChapterTextUtils:
    """Helpers for parsing flexible chapter lines."""

    TIME_PATTERN = re.compile(r"\b(?:(\d+):)?(\d{1,2}):(\d{2})\b|\b(\d{1,2}):(\d{2})\b")

    @staticmethod
    def normalize_timestamp(raw_value: str) -> str:
        """Convert m:ss or h:mm:ss into ffmpeg chapter timestamp format."""
        parts = [int(piece) for piece in raw_value.strip().split(":")]
        if len(parts) == 2:
            hours = 0
            minutes, seconds = parts
        elif len(parts) == 3:
            hours, minutes, seconds = parts
        else:
            raise ValueError(f"Unsupported timestamp: {raw_value}")
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.000"
