"""Background job service."""

from app.models.responses import JobResponse


class JobService:
    """Submit and inspect background jobs."""

    def __init__(self, job_repository) -> None:
        """Store the queue repository."""
        self._job_repository = job_repository

    def enqueue_create(self, request_payload: dict) -> JobResponse:
        """Queue a create workflow."""
        job = self._job_repository.enqueue("app.handlers.background_jobs.process_create_request", request_payload=request_payload)
        return JobResponse(job_id=job.id, status=job.get_status(), output_name=job.meta.get("output_name"))

    def enqueue_update(self, request_payload: dict) -> JobResponse:
        """Queue an update workflow."""
        job = self._job_repository.enqueue("app.handlers.background_jobs.process_update_request", request_payload=request_payload)
        return JobResponse(job_id=job.id, status=job.get_status())

    def get_status(self, job_id: str) -> JobResponse:
        """Read a job status from the queue backend."""
        job = self._job_repository.get_job(job_id)
        return JobResponse(job_id=job.id, status=job.get_status(), output_name=job.meta.get("output_name"))
