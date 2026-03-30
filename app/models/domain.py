"""Domain models used across services."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class ChapterEntry:
    """Normalized chapter representation."""

    index: int
    timestamp: str
    title: str


@dataclass(frozen=True)
class PosterCropSettings:
    """Represents client-provided poster crop and zoom settings."""

    zoom: float = 1.0
    offset_x: float = 0.5
    offset_y: float = 0.5
    mode: str = "cover"


@dataclass(frozen=True)
class ArtworkResult:
    """Represents a saved artwork file."""

    source_url: str
    saved_path: Path
    width: int
    height: int


@dataclass(frozen=True)
class DownloadResult:
    """Represents a saved media download."""

    title: str
    output_name: str
    video_path: Path
    aux_files: List[Path]


@dataclass(frozen=True)
class UpdateTarget:
    """Represents an existing output folder update target."""

    output_name: str
    mkv_path: Optional[Path]
    directory: Path
