"""Background job service."""

from datetime import datetime, timezone

from app.models.job_collection import JobCollection
from app.models.job_status import JobStatus
from app.models.responses import JobResponse


class JobService:
    """Submit and inspect background jobs."""

    def __init__(self, job_repository) -> None:
        """Store the queue repository."""
        self._job_repository = job_repository

    def enqueue_create(self, request_payload: dict) -> JobResponse:
        """Queue a create workflow."""
        job = self._job_repository.enqueue(
            "app.handlers.background_jobs.process_create_request",
            request_payload=request_payload,
        )
        job.meta["output_name"] = request_payload.get("output_name")
        job.save_meta()
        return self._to_job_response(job)

    def enqueue_update(self, request_payload: dict) -> JobResponse:
        """Queue an update workflow."""
        job = self._job_repository.enqueue(
            "app.handlers.background_jobs.process_update_request",
            request_payload=request_payload,
        )
        job.meta["output_name"] = request_payload.get("output_name")
        job.save_meta()
        return self._to_job_response(job)

    def get_status(self, job_id: str) -> JobResponse:
        """Read a job status from the queue backend."""
        job = self._job_repository.get_job(job_id)
        return self._to_job_response(job)

    def get_all_statuses(
        self,
        *,
        active_only: bool = True,
        group: str | None = None,
    ) -> JobCollection:
        """Return normalized job statuses for the UI."""
        jobs = self._job_repository.get_all_jobs()
        rows = [self._to_job_response(job) for job in jobs]
        collection = JobCollection.from_iterable(rows).sorted()

        if active_only:
            collection = collection.filter_active_only()

        collection = collection.filter_by_group(group)
        return collection

    def _to_job_response(self, job) -> JobResponse:
        """Map an RQ job to the app's response DTO."""
        created_at = getattr(job, "created_at", None)
        started_at = getattr(job, "started_at", None)
        finished_at = getattr(job, "ended_at", None)

        duration_seconds = None
        now = datetime.now(timezone.utc)

        if started_at and finished_at:
            started_at_for_calc = started_at
            finished_at_for_calc = finished_at

            if started_at_for_calc.tzinfo is None:
                started_at_for_calc = started_at_for_calc.replace(tzinfo=timezone.utc)
            if finished_at_for_calc.tzinfo is None:
                finished_at_for_calc = finished_at_for_calc.replace(tzinfo=timezone.utc)

            duration_seconds = max(
                0,
                int((finished_at_for_calc - started_at_for_calc).total_seconds()),
            )
        elif started_at:
            started_at_for_calc = started_at
            if started_at_for_calc.tzinfo is None:
                started_at_for_calc = started_at_for_calc.replace(tzinfo=timezone.utc)
            duration_seconds = max(0, int((now - started_at_for_calc).total_seconds()))

        return JobResponse(
            job_id=job.id,
            status=(job.get_status() or JobStatus.UNKNOWN.value),
            output_name=job.meta.get("output_name"),
            created_at=created_at,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
        )