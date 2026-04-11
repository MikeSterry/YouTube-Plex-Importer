from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class DownloadResult:
    title: str
    output_name: str
    video_path: Path
    aux_files: list[Path]