"""Persistence helpers for application settings."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.models.youtube_auth_settings import YoutubeAuthSettings


class SettingsRepository:
    """Read and write persisted settings artifacts."""

    def __init__(self, settings, filesystem_service) -> None:
        self._settings = settings
        self._filesystem_service = filesystem_service
        self._cookie_file = Path(settings.youtube_cookie_file)

    def load_youtube_auth_settings(self) -> YoutubeAuthSettings:
        """Return the current persisted YouTube auth settings."""
        configured = self._cookie_file.exists() and self._cookie_file.is_file() and self._cookie_file.stat().st_size > 0
        updated_at = None

        if configured:
            updated_at = datetime.fromtimestamp(
                self._cookie_file.stat().st_mtime
            ).strftime("%Y-%m-%d %H:%M:%S")

        return YoutubeAuthSettings(
            cookie_file_path=str(self._cookie_file),
            cookies_configured=configured,
            cookies_updated_at=updated_at,
        )

    def save_youtube_cookie_text(self, cookie_text: str) -> YoutubeAuthSettings:
        """Persist Netscape cookie text to the configured cookie file path."""
        self._filesystem_service.ensure_directory(self._cookie_file.parent)

        tmp_path = self._cookie_file.with_suffix(f"{self._cookie_file.suffix}.tmp")
        tmp_path.write_text(cookie_text, encoding="utf-8")
        self._filesystem_service.normalize_file(tmp_path)

        tmp_path.replace(self._cookie_file)
        self._filesystem_service.normalize_file(self._cookie_file)

        return self.load_youtube_auth_settings()

    def clear_youtube_cookie_text(self) -> YoutubeAuthSettings:
        """Delete the saved cookie file when present."""
        if self._cookie_file.exists():
            self._cookie_file.unlink()

        return self.load_youtube_auth_settings()

    def get_youtube_cookie_file_path(self) -> str | None:
        """Return the configured cookie file path only when a valid file exists."""
        settings = self.load_youtube_auth_settings()
        if not settings.cookies_configured:
            return None
        return settings.cookie_file_path