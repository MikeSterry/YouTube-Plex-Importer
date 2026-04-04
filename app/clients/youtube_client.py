# app/clients/youtube_client.py
"""YouTube download integration using yt-dlp."""

from __future__ import annotations

import re
import time
from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.exceptions import YoutubeDownloadError
from app.models.domain import DownloadResult
from app.utils.file_utils import FileNameUtils
from app.utils.logger_factory import get_logger

LOGGER = get_logger(__name__)


class YoutubeClient:
    """Client responsible for downloading YouTube content."""

    def __init__(self, settings, filesystem_service, settings_service=None) -> None:
        """Store collaborator dependencies."""
        self._settings = settings
        self._filesystem_service = filesystem_service
        self._settings_service = settings_service

    def download_best_mkv(
        self,
        youtube_url: str,
        work_dir: Path,
        desired_output_name: str | None = None,
    ) -> DownloadResult:
        """Download the highest quality video/audio and mux it into MKV."""
        LOGGER.info("Extracting YouTube metadata.")
        info = self._extract_info(youtube_url)

        output_name = self._build_output_name(info, desired_output_name)
        target_template = str(work_dir / f"{output_name}.%(ext)s")

        LOGGER.info("Downloading YouTube media.", extra={"output_name": output_name})
        self._download_media(youtube_url, target_template)

        video_path = self._find_video_path(work_dir, output_name)
        LOGGER.info("Located final MKV.", extra={"video_path": str(video_path)})

        return DownloadResult(
            title=info.get("title", output_name),
            output_name=output_name,
            video_path=video_path,
            aux_files=[path for path in work_dir.iterdir() if path.is_file()],
        )

    def _build_output_name(self, info: dict, desired_output_name: str | None) -> str:
        """Choose a readable output base name for the downloaded media."""
        if desired_output_name:
            base_name = FileNameUtils.sanitize_display_name(desired_output_name)
        else:
            fallback_name = info.get("title") or info.get("id") or "video"
            base_name = FileNameUtils.sanitize_display_name(fallback_name)

        upload_year = self._extract_upload_year(info)
        return self._apply_year_suffix(base_name, upload_year)

    def _extract_info(self, youtube_url: str) -> dict:
        """Read video metadata without downloading the file."""
        with YoutubeDL(self._build_common_options()) as ydl:
            return ydl.extract_info(youtube_url, download=False)

    def _download_media(self, youtube_url: str, output_template: str) -> None:
        """Download media with yt-dlp and retry transient failures."""
        options = self._build_common_options()
        options.update(
            {
                "format": self._settings.ytdlp_format,
                "merge_output_format": "mkv",
                "outtmpl": output_template,
            }
        )

        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            try:
                with YoutubeDL(options) as ydl:
                    ydl.download([youtube_url])
                return
            except DownloadError as exc:
                if attempt < max_attempts:
                    time.sleep(attempt * 5)
                    continue

                message = str(exc)
                if self._is_bot_challenge_error(message) and not self._get_cookiefile():
                    message = (
                        f"{message} "
                        "Configure YouTube cookies on the Settings page and try again."
                    )

                raise YoutubeDownloadError(message) from exc

    def _build_common_options(self) -> dict:
        """Build yt-dlp options shared by metadata and download operations."""
        options = {
            "quiet": True,
            "noprogress": True,
            "skip_download": False,
            "js_runtimes": self._settings.ytdlp_js_runtimes_dict,
            "remote_components": self._settings.ytdlp_remote_components_set,
            "socket_timeout": self._settings.ytdlp_socket_timeout,
            "retries": self._settings.ytdlp_retries,
            "fragment_retries": self._settings.ytdlp_fragment_retries,
            "file_access_retries": self._settings.ytdlp_file_access_retries,
            "extractor_retries": self._settings.ytdlp_extractor_retries,
            "retry_sleep_functions": {
                "http": self._build_retry_sleep(self._settings.ytdlp_retry_sleep_http),
                "fragment": self._build_retry_sleep(
                    self._settings.ytdlp_retry_sleep_fragment
                ),
                "file_access": self._build_retry_sleep(
                    self._settings.ytdlp_retry_sleep_file_access
                ),
                "extractor": self._build_retry_sleep(
                    self._settings.ytdlp_retry_sleep_extractor
                ),
            },
            "http_chunk_size": self._settings.ytdlp_http_chunk_size,
            "throttledratelimit": self._parse_rate(self._settings.ytdlp_throttled_rate),
        }

        cookiefile = self._get_cookiefile()
        if cookiefile:
            options["cookiefile"] = cookiefile

        return options

    def _find_video_path(self, work_dir: Path, output_name: str) -> Path:
        """Locate the final MKV after yt-dlp completes."""
        for candidate in work_dir.glob(f"{output_name}*.mkv"):
            self._filesystem_service.normalize_file(candidate)
            return candidate
        raise FileNotFoundError("Unable to locate downloaded MKV file.")

    def _extract_upload_year(self, info: dict) -> str | None:
        """Extract the year from yt-dlp upload_date metadata."""
        upload_date = info.get("upload_date")
        if not upload_date:
            return None

        cleaned = str(upload_date).strip()
        match = re.match(r"^(\d{4})", cleaned)
        if not match:
            return None

        return match.group(1)

    def _apply_year_suffix(self, base_name: str, year: str | None) -> str:
        """Append or replace a trailing ' (YYYY)' suffix on a filename stem."""
        cleaned_base = re.sub(r"\s\(\d{4}\)$", "", base_name).rstrip()
        if not year:
            return cleaned_base
        return f"{cleaned_base} ({year})"

    def _get_cookiefile(self) -> str | None:
        """Return the configured YouTube cookie file, if available."""
        if self._settings_service is None:
            return None

        getter = getattr(self._settings_service, "get_youtube_cookie_file_path", None)
        if getter is None:
            return None

        return getter()

    def _is_bot_challenge_error(self, message: str) -> bool:
        """Return True when yt-dlp reports YouTube's anti-bot sign-in challenge."""
        normalized = message.lower()
        return "sign in to confirm" in normalized and "not a bot" in normalized

    def _build_retry_sleep(self, expr: str):
        """Build a yt-dlp retry sleep function from a simple config string."""
        if not expr:
            return None

        if expr.isdigit():
            seconds = float(expr)
            return lambda *_args, **_kwargs: seconds

        if expr.startswith("linear="):
            return self._build_linear_sleep(expr.removeprefix("linear="))

        if expr.startswith("exp="):
            return self._build_exp_sleep(expr.removeprefix("exp="))

        return None

    def _build_linear_sleep(self, payload: str):
        """Build a linear backoff retry sleep function."""
        parts = payload.split(":")
        start = float(parts[0]) if len(parts) > 0 and parts[0] else 1.0
        end = float(parts[1]) if len(parts) > 1 and parts[1] else start
        step = float(parts[2]) if len(parts) > 2 and parts[2] else 1.0

        def linear_sleep(attempt, *_args, **_kwargs):
            value = start + max(attempt - 1, 0) * step
            return min(value, end)

        return linear_sleep

    def _build_exp_sleep(self, payload: str):
        """Build an exponential backoff retry sleep function."""
        parts = payload.split(":")
        start = float(parts[0]) if len(parts) > 0 and parts[0] else 1.0
        end = float(parts[1]) if len(parts) > 1 and parts[1] else start
        base = float(parts[2]) if len(parts) > 2 and parts[2] else 2.0

        def exp_sleep(attempt, *_args, **_kwargs):
            value = start * (base ** max(attempt - 1, 0))
            return min(value, end)

        return exp_sleep

    def _parse_rate(self, value: str | None) -> int | None:
        """Parse a human-readable byte rate like 100K or 4M."""
        if not value:
            return None

        cleaned = value.strip().upper()
        suffixes = {
            "K": 1024,
            "M": 1024 * 1024,
            "G": 1024 * 1024 * 1024,
        }

        if cleaned[-1] in suffixes:
            return int(float(cleaned[:-1]) * suffixes[cleaned[-1]])

        return int(float(cleaned))