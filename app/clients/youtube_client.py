from __future__ import annotations

import re
import time
from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, ExtractorError

from app.exceptions import YoutubeDownloadError, YoutubeRateLimitError
from app.models.download_result import DownloadResult


_RATE_LIMIT_PATTERNS = (
    "current session has been rate-limited by youtube",
    "this content isn't available, try again later",
    "try again later. the current session has been rate-limited",
)


def _is_rate_limited_message(message: str) -> bool:
    normalized = (message or "").lower()
    return any(pattern in normalized for pattern in _RATE_LIMIT_PATTERNS)


def _raise_mapped_youtube_error(exc: Exception, settings_service) -> None:
    message = str(exc)
    normalized = message.lower()

    if _is_rate_limited_message(message):
        raise YoutubeRateLimitError(
            "YouTube rate-limited the current session. "
            "The job was stopped and left in Failed status. "
            "Retry it manually later."
        ) from exc

    has_cookiefile = bool(settings_service.get_youtube_cookie_file_path())

    if (
        "sign in to confirm you’re not a bot" in normalized
        or "sign in to confirm you're not a bot" in normalized
    ):
        if not has_cookiefile:
            raise YoutubeDownloadError(
                f"{message} Configure YouTube cookies on the Settings page and try again."
            ) from exc
        raise YoutubeDownloadError(message) from exc

    raise YoutubeDownloadError(message) from exc


class YoutubeClient:
    def __init__(self, settings, filesystem_service, settings_service) -> None:
        self._settings = settings
        self._filesystem_service = filesystem_service
        self._settings_service = settings_service

    def download_best_mkv(
        self,
        youtube_url: str,
        work_dir: Path,
        desired_output_name: str | None = None,
    ) -> DownloadResult:
        info = self._extract_info(youtube_url)
        output_name = self._build_output_name(info, desired_output_name)
        output_template = str(work_dir / f"{output_name}.%(ext)s")

        self._download_media(youtube_url, output_template)
        video_path = self._find_video_path(work_dir, output_name)

        aux_files = [path for path in work_dir.iterdir() if path.is_file()]

        return DownloadResult(
            title=info.get("title") or "video",
            output_name=output_name,
            video_path=video_path,
            aux_files=aux_files,
        )

    def _extract_info(self, youtube_url: str) -> dict:
        """Read video metadata without downloading the file."""
        options = self._build_common_options()
        try:
            with YoutubeDL(options) as ydl:
                return ydl.extract_info(youtube_url, download=False)
        except (DownloadError, ExtractorError) as exc:
            _raise_mapped_youtube_error(exc, self._settings_service)

    def _download_media(self, youtube_url: str, output_template: str) -> None:
        """Download media with retry handling."""
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
            except (DownloadError, ExtractorError) as exc:
                if _is_rate_limited_message(str(exc)):
                    _raise_mapped_youtube_error(exc, self._settings_service)

                if attempt < max_attempts:
                    time.sleep(attempt * 5)
                    continue

                _raise_mapped_youtube_error(exc, self._settings_service)

    def _build_common_options(self) -> dict:
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
            "http_chunk_size": self._settings.ytdlp_http_chunk_size,
        }

        throttled_rate = self._parse_rate(self._settings.ytdlp_throttled_rate)
        if throttled_rate is not None:
            options["throttledratelimit"] = throttled_rate

        retry_sleep_http = self._build_retry_sleep(self._settings.ytdlp_retry_sleep_http)
        retry_sleep_fragment = self._build_retry_sleep(
            self._settings.ytdlp_retry_sleep_fragment
        )
        retry_sleep_file_access = self._build_retry_sleep(
            self._settings.ytdlp_retry_sleep_file_access
        )
        retry_sleep_extractor = self._build_retry_sleep(
            self._settings.ytdlp_retry_sleep_extractor
        )

        retry_sleep = {}
        if retry_sleep_http is not None:
            retry_sleep["http"] = retry_sleep_http
        if retry_sleep_fragment is not None:
            retry_sleep["fragment"] = retry_sleep_fragment
        if retry_sleep_file_access is not None:
            retry_sleep["file_access"] = retry_sleep_file_access
        if retry_sleep_extractor is not None:
            retry_sleep["extractor"] = retry_sleep_extractor
        if retry_sleep:
            options["retry_sleep_functions"] = retry_sleep

        cookie_file = self._settings_service.get_youtube_cookie_file_path()
        if cookie_file:
            options["cookiefile"] = cookie_file

        return options

    def _build_output_name(
        self, info: dict, desired_output_name: str | None = None
    ) -> str:
        base_name = (
            (desired_output_name or "").strip()
            or (info.get("title") or "").strip()
            or (info.get("id") or "").strip()
            or "video"
        )

        base_name = re.sub(r"\s*\(\d{4}\)\s*$", "", base_name).strip()

        upload_year = self._extract_upload_year(info)
        if upload_year:
            return f"{base_name} ({upload_year})"

        return base_name

    def _extract_upload_year(self, info: dict) -> str | None:
        upload_date = (info or {}).get("upload_date")
        if not upload_date or len(upload_date) < 4:
            return None
        return str(upload_date)[:4]

    def _find_video_path(self, work_dir: Path, output_name: str) -> Path:
        expected_path = work_dir / f"{output_name}.mkv"
        if expected_path.exists():
            self._filesystem_service.normalize_file(expected_path)
            return expected_path

        for path in work_dir.glob("*.mkv"):
            self._filesystem_service.normalize_file(path)
            return path

        raise FileNotFoundError("Unable to locate downloaded MKV file")

    def _parse_rate(self, value: str | None) -> int | None:
        if not value:
            return None

        text = str(value).strip()
        if not text:
            return None

        match = re.fullmatch(r"(\d+)([KMG])?", text, re.IGNORECASE)
        if not match:
            raise ValueError(f"Invalid rate value: {value}")

        amount = int(match.group(1))
        suffix = (match.group(2) or "").upper()

        if suffix == "K":
            return amount * 1024
        if suffix == "M":
            return amount * 1024 * 1024
        if suffix == "G":
            return amount * 1024 * 1024 * 1024
        return amount

    def _build_retry_sleep(self, expression: str | None):
        if expression is None:
            return None

        text = str(expression).strip()
        if not text:
            return None

        if text.startswith("linear="):
            return self._build_linear_sleep(text.split("=", 1)[1])

        if text.startswith("exp="):
            return self._build_exp_sleep(text.split("=", 1)[1])

        seconds = float(text)

        def fixed_sleep(_attempt: int) -> float:
            return seconds

        return fixed_sleep

    def _build_linear_sleep(self, spec: str):
        start_text, stop_text, step_text = spec.split(":")
        start = float(start_text)
        stop = float(stop_text)
        step = float(step_text)

        def linear_sleep(attempt: int) -> float:
            value = start + max(0, attempt - 1) * step
            return min(value, stop)

        return linear_sleep

    def _build_exp_sleep(self, spec: str):
        start_text, stop_text, base_text = spec.split(":")
        start = float(start_text)
        stop = float(stop_text)
        base = float(base_text)

        def exp_sleep(attempt: int) -> float:
            value = start * (base ** max(0, attempt - 1))
            return min(value, stop)

        return exp_sleep