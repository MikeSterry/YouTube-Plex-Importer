"""YouTube download integration using yt-dlp."""

from pathlib import Path

from yt_dlp import YoutubeDL

from app.models.domain import DownloadResult
from app.utils.file_utils import FileNameUtils
from app.utils.logger_factory import get_logger


LOGGER = get_logger(__name__)


class YoutubeClient:
    """Client responsible for downloading YouTube content."""

    def __init__(self, settings, filesystem_service) -> None:
        """Store collaborator dependencies."""
        self._settings = settings
        self._filesystem_service = filesystem_service

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
            return FileNameUtils.sanitize_display_name(desired_output_name)

        fallback_name = info.get("title") or info.get("id") or "video"
        return FileNameUtils.sanitize_display_name(fallback_name)

    def _extract_info(self, youtube_url: str) -> dict:
        """Read video metadata without downloading the file."""
        with YoutubeDL(self._build_common_options()) as ydl:
            return ydl.extract_info(youtube_url, download=False)

    def _download_media(self, youtube_url: str, output_template: str) -> None:
        """Download the actual media to disk."""
        options = self._build_common_options()
        options.update(
            {
                "format": self._settings.ytdlp_format,
                "merge_output_format": "mkv",
                "outtmpl": output_template,
            }
        )

        with YoutubeDL(options) as ydl:
            ydl.download([youtube_url])


    def _build_common_options(self) -> dict:
        """Build yt-dlp options shared by metadata and download operations."""
        return {
            "quiet": True,
            "noprogress": True,
            "skip_download": False,
            "js_runtimes": self._settings.ytdlp_js_runtimes_dict,
            "remote_components": self._settings.ytdlp_remote_components_set,
        }


    def _find_video_path(self, work_dir: Path, output_name: str) -> Path:
        """Locate the final MKV after yt-dlp completes."""
        for candidate in work_dir.glob(f"{output_name}*.mkv"):
            self._filesystem_service.normalize_file(candidate)
            return candidate

        raise FileNotFoundError("Unable to locate downloaded MKV file.")
