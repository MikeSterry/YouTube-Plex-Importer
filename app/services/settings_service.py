"""Business logic for persisted app settings."""

from __future__ import annotations

from app.models.youtube_auth_settings import YoutubeAuthSettings


class SettingsService:
    """Validate and persist user-editable settings."""

    def __init__(self, settings_repository) -> None:
        self._settings_repository = settings_repository

    def get_youtube_auth_settings(self) -> YoutubeAuthSettings:
        """Return the current saved YouTube auth settings."""
        return self._settings_repository.load_youtube_auth_settings()

    def save_youtube_cookie_text(self, raw_cookie_text: str) -> YoutubeAuthSettings:
        """Validate and persist yt-dlp-compatible Netscape cookies."""
        normalized = self._normalize_cookie_text(raw_cookie_text)
        self._validate_youtube_cookie_text(normalized)
        return self._settings_repository.save_youtube_cookie_text(normalized)

    def clear_youtube_cookie_text(self) -> YoutubeAuthSettings:
        """Remove saved YouTube cookie data."""
        return self._settings_repository.clear_youtube_cookie_text()

    def get_youtube_cookie_file_path(self) -> str | None:
        """Return the cookie file path only when cookies are configured."""
        return self._settings_repository.get_youtube_cookie_file_path()

    def _normalize_cookie_text(self, raw_cookie_text: str) -> str:
        """Normalize line endings and trim outer whitespace."""
        normalized = (raw_cookie_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if normalized:
            normalized = f"{normalized}\n"
        return normalized

    def _validate_youtube_cookie_text(self, cookie_text: str) -> None:
        """Validate that the supplied cookie text resembles Netscape cookies."""
        if not cookie_text.strip():
            raise ValueError("Cookie data is required.")

        lines = [
            line.strip()
            for line in cookie_text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        if not lines:
            raise ValueError("Cookie data is empty.")

        valid_cookie_lines = []
        for line in lines:
            parts = line.split("\t")
            if len(parts) >= 7:
                valid_cookie_lines.append(parts)

        if not valid_cookie_lines:
            raise ValueError(
                "Cookie data must be in Netscape cookies.txt format."
            )

        has_google_or_youtube_domain = any(
            ".youtube.com" in parts[0] or "youtube.com" in parts[0] or ".google.com" in parts[0] or "google.com" in parts[0]
            for parts in valid_cookie_lines
        )
        if not has_google_or_youtube_domain:
            raise ValueError(
                "Cookie data must include at least one youtube.com or google.com cookie."
            )