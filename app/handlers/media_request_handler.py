"""Use-case orchestration for create and update flows."""

from dataclasses import asdict
from pathlib import Path
import shutil

from rq import get_current_job

from app.models.requests import CreateMediaRequest, UpdateMediaRequest
from app.utils.constants import CHAPTER_FILENAME


class MediaRequestHandler:
    """Coordinate the full request lifecycle."""

    def __init__(
        self,
        output_repository,
        media_service,
        image_service,
        chapter_service,
        metadata_service,
        job_service,
        filesystem_service,
    ) -> None:
        """Store services used for high-level workflows."""
        self._output_repository = output_repository
        self._media_service = media_service
        self._image_service = image_service
        self._chapter_service = chapter_service
        self._metadata_service = metadata_service
        self._job_service = job_service
        self._filesystem_service = filesystem_service

    def submit_create(self, request: CreateMediaRequest):
        """Queue a create request."""
        return self._job_service.enqueue_create(asdict(request))

    def submit_update(self, request: UpdateMediaRequest):
        """Queue an update request."""
        return self._job_service.enqueue_update(asdict(request))

    def process_create(self, request: CreateMediaRequest) -> dict:
        """Execute the create workflow synchronously for the worker."""
        job = get_current_job()
        job_id = job.id if job else None

        download_result, work_dir, final_dir = self._media_service.download_youtube_video(
            request.youtube_url,
            request.output_name,
            job_id,
        )

        final_video = self._media_service.finalize_video(download_result.video_path, final_dir)

        if request.chapters_text:
            final_video = self._apply_chapters(request.chapters_text, final_dir, final_video)

        if request.poster_url:
            self._image_service.process_poster(
                request.poster_url,
                final_dir,
                request.poster_crop_settings,
            )

        if request.background_url:
            self._image_service.process_background(request.background_url, final_dir)

        self._cleanup(work_dir)
        return {"output_name": download_result.output_name, "video_path": str(final_video)}

    def process_update(self, request: UpdateMediaRequest) -> dict:
        """Execute the update workflow synchronously for the worker."""
        target = self._output_repository.find_update_target(request.output_name)

        if request.chapters_text and target.mkv_path:
            self._apply_chapters(request.chapters_text, target.directory, target.mkv_path)

        if request.poster_url:
            self._image_service.process_poster(
                request.poster_url,
                target.directory,
                request.poster_crop_settings,
            )
        elif request.local_poster_file:
            poster_path = self._output_repository.resolve_poster_file(
                request.output_name,
                request.local_poster_file,
            )
            self._image_service.process_local_poster(
                poster_path,
                request.poster_crop_settings,
            )

        if request.background_url:
            self._image_service.process_background(request.background_url, target.directory)

        return {
            "output_name": target.output_name,
            "video_path": str(target.mkv_path) if target.mkv_path else None,
        }

    def _apply_chapters(self, chapters_text: str, output_dir: Path, source_video: Path) -> Path:
        """Parse, write, and merge chapter metadata into a video."""
        chapters = self._chapter_service.parse(chapters_text)
        chapter_text = self._chapter_service.to_metadata_text(chapters)
        chapter_file = self._filesystem_service.write_text(output_dir / CHAPTER_FILENAME, chapter_text)
        temp_output = output_dir / f"{source_video.stem}.chapters.mkv"
        merged_video = self._metadata_service.merge_chapters(source_video, chapter_file, temp_output)
        shutil.move(str(merged_video), str(source_video))
        self._filesystem_service.normalize_file(source_video)
        return source_video

    def _cleanup(self, work_dir: Path) -> None:
        """Best-effort cleanup of temporary work directories."""
        shutil.rmtree(work_dir, ignore_errors=True)