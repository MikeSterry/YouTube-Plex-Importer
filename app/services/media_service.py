"""Media orchestration primitives."""

from pathlib import Path
from uuid import uuid4

from app.models.domain import DownloadResult


class MediaService:
    """Coordinate download and finalization of video files."""

    def __init__(self, settings, filesystem_service, output_repository, youtube_client) -> None:
        """Store dependencies used during media processing."""
        self._settings = settings
        self._filesystem_service = filesystem_service
        self._output_repository = output_repository
        self._youtube_client = youtube_client

    def download_youtube_video(self, youtube_url: str, desired_output_name: str | None = None) -> tuple[DownloadResult, Path, Path]:
        """Download a YouTube video into a work directory and prepare the output folder."""
        work_dir = self._output_repository.create_work_dir(f"job-{uuid4().hex}")
        download_result = self._youtube_client.download_best_mkv(youtube_url, work_dir, desired_output_name)
        final_dir = self._output_repository.create_output_dir(download_result.output_name)
        return download_result, work_dir, final_dir

    def finalize_video(self, video_path: Path, final_dir: Path) -> Path:
        """Move the final video into the output directory."""
        return self._filesystem_service.move_to_directory(video_path, final_dir)
