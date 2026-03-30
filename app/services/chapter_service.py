"""Chapter parsing and serialization service."""

import re
from typing import List

from app.models.domain import ChapterEntry
from app.utils.chapter_utils import ChapterTextUtils


class ChapterService:
    """Parse free-form chapter text and render MKV chapter metadata."""

    def parse(self, raw_text: str | None) -> List[ChapterEntry]:
        """Parse raw chapter text into normalized chapter entries."""
        if not raw_text or not raw_text.strip():
            return []

        entries = []
        for index, line in enumerate(self._non_empty_lines(raw_text), start=1):
            timestamp, title = self._extract_parts(line)
            entries.append(ChapterEntry(index=index, timestamp=timestamp, title=title))
        return entries

    def to_metadata_text(self, chapters: List[ChapterEntry]) -> str:
        """Render chapter entries into ffmetadata text."""
        # lines = [";FFMETADATA1"]
        lines = []
        for chapter in chapters:
            lines.append(f"CHAPTER{chapter.index:02d}={chapter.timestamp}")
            lines.append(f"CHAPTER{chapter.index:02d}NAME={chapter.title}")
        return "\n".join(lines) + "\n"

    def _non_empty_lines(self, raw_text: str) -> List[str]:
        """Return stripped non-empty lines from the raw chapter text."""
        return [line.strip() for line in raw_text.splitlines() if line.strip()]

    def _extract_parts(self, line: str) -> tuple[str, str]:
        """Split a flexible line into timestamp and title components."""
        time_match = re.search(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", line)
        if not time_match:
            raise ValueError(f"Unable to parse chapter line: {line}")

        raw_time = time_match.group(0)
        title = self._remove_time_and_separators(line, raw_time)
        return ChapterTextUtils.normalize_timestamp(raw_time), title

    def _remove_time_and_separators(self, line: str, raw_time: str) -> str:
        """Remove a time token and clean surrounding separators."""
        title = line.replace(raw_time, "", 1)
        title = re.sub(r"^\s*[-–—:]\s*", "", title)
        title = re.sub(r"\s*[-–—:]\s*$", "", title)
        title = re.sub(r"\s{2,}", " ", title).strip()
        if not title:
            raise ValueError(f"Chapter title missing for line: {line}")
        return title