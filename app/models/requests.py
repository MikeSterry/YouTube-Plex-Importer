"""Request DTOs."""

from dataclasses import dataclass
from typing import Optional

from app.models.domain import PosterCropSettings


@dataclass(frozen=True)
class CreateMediaRequest:
    """Create request payload."""

    youtube_url: str
    output_name: Optional[str] = None
    poster_url: Optional[str] = None
    background_url: Optional[str] = None
    chapters_text: Optional[str] = None
    poster_crop_settings: Optional[PosterCropSettings] = None


@dataclass(frozen=True)
class UpdateMediaRequest:
    """Update request payload."""

    output_name: str
    poster_url: Optional[str] = None
    local_poster_file: Optional[str] = None
    background_url: Optional[str] = None
    chapters_text: Optional[str] = None
    poster_crop_settings: Optional[PosterCropSettings] = None
