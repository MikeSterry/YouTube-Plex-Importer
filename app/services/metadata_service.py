"""Metadata merge operations for MKV files."""

from pathlib import Path
import shutil
import subprocess


class MetadataService:
    """Merge chapters into MKV files."""

    def __init__(self, settings, filesystem_service) -> None:
        """Store collaborators needed by the service."""
        self._settings = settings
        self._filesystem_service = filesystem_service

    def merge_chapters(self, source_video: Path, chapter_file: Path, destination_video: Path) -> Path:
        """Merge real Matroska chapters into an MKV using mkvmerge."""
        temp_output = self._build_temp_output_path(destination_video)
        self._run_mkvmerge(source_video, chapter_file, temp_output)
        self._replace_destination(temp_output, destination_video)
        return self._filesystem_service.normalize_file(destination_video)

    def _build_temp_output_path(self, destination_video: Path) -> Path:
        """Build a temporary output path in the same directory as the destination."""
        return destination_video.with_name(f"{destination_video.stem}.chapters.tmp{destination_video.suffix}")

    def _run_mkvmerge(self, source_video: Path, chapter_file: Path, temp_output: Path) -> None:
        """Run mkvmerge to attach chapters to the MKV."""
        command = [
            self._settings.mkvmerge_bin,
            "-o",
            str(temp_output),
            "--chapters",
            str(chapter_file),
            str(source_video),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)

    def _replace_destination(self, temp_output: Path, destination_video: Path) -> None:
        """Atomically replace the destination file with the merged output."""
        shutil.move(str(temp_output), str(destination_video))
        self._filesystem_service.normalize_file(destination_video)