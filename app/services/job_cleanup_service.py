"""Cleanup rules for failed or discarded jobs."""

from pathlib import Path


class JobCleanupService:
    """Remove filesystem artifacts associated with failed jobs."""

    def __init__(self, settings, filesystem_service) -> None:
        """Store settings and filesystem helpers."""
        self._settings = settings
        self._filesystem_service = filesystem_service

    def cleanup_failed_job_artifacts(self, metadata: dict) -> None:
        """Remove work directories and partial create outputs when safe."""
        work_dir_name = (metadata.get("work_dir_name") or "").strip()
        job_type = (metadata.get("job_type") or "").strip().lower()
        output_name = (metadata.get("output_name") or "").strip()

        if work_dir_name:
            work_dir = self._safe_join(Path(self._settings.inprogress_dir), work_dir_name)
            if work_dir is not None:
                self._filesystem_service.remove_directory(work_dir)

        if job_type == "create" and output_name:
            output_dir = self._safe_join(Path(self._settings.output_dir), output_name)
            if output_dir is not None:
                self._filesystem_service.remove_directory(output_dir)

    def _safe_join(self, base: Path, relative_name: str) -> Path | None:
        """Resolve a child path safely beneath a configured base directory."""
        candidate = (base / relative_name).resolve()
        base_resolved = base.resolve()

        if candidate == base_resolved:
            return None
        if base_resolved not in candidate.parents:
            return None

        return candidate