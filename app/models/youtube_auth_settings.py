"""Models for persisted YouTube authentication settings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class YoutubeAuthSettings:
    """Represents the saved YouTube authentication cookie configuration."""

    cookie_file_path: str
    cookies_configured: bool
    cookies_updated_at: str | None = None