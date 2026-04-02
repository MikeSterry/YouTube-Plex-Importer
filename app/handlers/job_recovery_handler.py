"""Use-case orchestration for retrying and deleting failed jobs."""

class JobRecoveryHandler:
    """Coordinate recovery actions for failed/stopped/canceled jobs."""

    def __init__(self, job_service, cleanup_service) -> None:
        """Store collaborators used for job recovery."""
        self._job_service = job_service
        self._cleanup_service = cleanup_service

    def retry_job(self, job_id: str):
        """Retry a failed job after cleanup."""
        return self._job_service.retry_job(job_id, cleanup_service=self._cleanup_service)

    def delete_job(self, job_id: str) -> None:
        """Delete a failed job after cleanup."""
        self._job_service.delete_job(job_id, cleanup_service=self._cleanup_service)