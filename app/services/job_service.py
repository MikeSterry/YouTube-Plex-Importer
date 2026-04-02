"""Background job service."""

from datetime import datetime, timezone

from app.models.job_collection import JobCollection
from app.models.job_status import JobStatus
from app.models.responses import JobResponse


CREATE_FUNC_PATH = "app.handlers.background_jobs.process_create_request"
UPDATE_FUNC_PATH = "app.handlers.background_jobs.process_update_request"
DEFAULT_RESULT_TTL_SECONDS = 7 * 24 * 60 * 60
DEFAULT_FAILURE_TTL_SECONDS = 30 * 24 * 60 * 60
RECOVERABLE_STATUSES = {
    JobStatus.FAILED,
    JobStatus.STOPPED,
    JobStatus.CANCELED,
}


class JobService:
    """Submit and inspect background jobs."""

    def __init__(self, job_repository) -> None:
        """Store the queue repository."""
        self._job_repository = job_repository

    def enqueue_create(self, request_payload: dict) -> JobResponse:
        """Queue a create workflow."""
        job = self._enqueue_job(
            func_path=CREATE_FUNC_PATH,
            request_payload=request_payload,
            job_type="create",
        )
        return self._to_job_response(job)

    def enqueue_update(self, request_payload: dict) -> JobResponse:
        """Queue an update workflow."""
        job = self._enqueue_job(
            func_path=UPDATE_FUNC_PATH,
            request_payload=request_payload,
            job_type="update",
        )
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

    def retry_job(self, job_id: str, cleanup_service) -> JobResponse:
        """Retry a failed/stopped/canceled job after cleanup."""
        job = self._job_repository.get_job(job_id)
        self._validate_recoverable(job)

        metadata = self._build_recovery_metadata(job)
        cleanup_service.cleanup_failed_job_artifacts(metadata)

        replacement = self._enqueue_job(
            func_path=metadata["func_path"],
            request_payload=metadata["request_payload"],
            job_type=metadata["job_type"],
        )
        replacement.meta["retried_from_job_id"] = job.id
        replacement.save_meta()

        return self._to_job_response(replacement)

    def delete_job(self, job_id: str, cleanup_service) -> None:
        """Delete a failed/stopped/canceled job after cleanup."""
        job = self._job_repository.get_job(job_id)
        self._validate_recoverable(job)

        metadata = self._build_recovery_metadata(job)
        cleanup_service.cleanup_failed_job_artifacts(metadata)
        self._job_repository.delete_job(job.id)

    def _enqueue_job(self, *, func_path: str, request_payload: dict, job_type: str):
        """Enqueue a job and attach metadata used by status/recovery flows."""
        job = self._job_repository.enqueue(
            func_path,
            request_payload=request_payload,
            result_ttl=DEFAULT_RESULT_TTL_SECONDS,
            failure_ttl=DEFAULT_FAILURE_TTL_SECONDS,
        )

        job.meta["job_type"] = job_type
        job.meta["func_path"] = func_path
        job.meta["request_payload"] = request_payload
        job.meta["output_name"] = request_payload.get("output_name")
        job.meta["work_dir_name"] = f"job-{job.id}" if job_type == "create" else None
        job.save_meta()
        return job

    def _validate_recoverable(self, job) -> None:
        """Ensure a job can be retried or deleted from the UI."""
        status = JobStatus.from_value(job.get_status())
        if status not in RECOVERABLE_STATUSES:
            raise ValueError(f"Job {job.id} is not recoverable from status {status.value}.")

    def _build_recovery_metadata(self, job) -> dict:
        """Build cleanup/retry metadata from stored job information."""
        request_payload = dict(job.meta.get("request_payload") or {})
        job_type = (job.meta.get("job_type") or "").strip().lower()

        if job_type not in {"create", "update"}:
            raise ValueError(f"Job {job.id} is missing recovery metadata.")

        output_name = (
            (job.meta.get("output_name") or "").strip()
            or (request_payload.get("output_name") or "").strip()
        )

        func_path = (job.meta.get("func_path") or "").strip()
        if not func_path:
            func_path = CREATE_FUNC_PATH if job_type == "create" else UPDATE_FUNC_PATH

        work_dir_name = (job.meta.get("work_dir_name") or "").strip()
        if not work_dir_name and job_type == "create":
            work_dir_name = f"job-{job.id}"

        return {
            "job_id": job.id,
            "job_type": job_type,
            "func_path": func_path,
            "request_payload": request_payload,
            "output_name": output_name,
            "work_dir_name": work_dir_name,
        }

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
            error_summary=self._build_error_summary(getattr(job, "exc_info", None)),
        )

    def _build_error_summary(self, exc_info: str | None) -> str | None:
        """Return a compact single-line error summary for the status page."""
        if not exc_info:
            return None

        lines = [line.strip() for line in exc_info.splitlines() if line.strip()]
        if not lines:
            return None

        for line in reversed(lines):
            if line and not line.startswith("File "):
                return line

        return lines[-1]