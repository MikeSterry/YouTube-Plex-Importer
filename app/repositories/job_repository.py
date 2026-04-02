"""Repository wrapper around the background queue."""

from rq.job import Job
from rq.registry import (
    DeferredJobRegistry,
    FailedJobRegistry,
    FinishedJobRegistry,
    ScheduledJobRegistry,
    StartedJobRegistry,
)


class JobRepository:
    """Encapsulates queue access."""

    def __init__(self, queue) -> None:
        """Store the underlying RQ queue."""
        self._queue = queue

    def enqueue(self, func_path: str, **kwargs):
        """Enqueue a callable by import path with kwargs."""
        return self._queue.enqueue(func_path, **kwargs)

    def get_job(self, job_id: str):
        """Fetch a job by id from the current queue connection."""
        return Job.fetch(job_id, connection=self._queue.connection)

    def get_all_jobs(self):
        """Return all known jobs across queue and registries."""
        connection = self._queue.connection
        job_ids: list[str] = []
        seen: set[str] = set()

        def add_ids(ids):
            for job_id in ids:
                if job_id not in seen:
                    seen.add(job_id)
                    job_ids.append(job_id)

        add_ids(self._queue.job_ids)
        add_ids(StartedJobRegistry(queue=self._queue).get_job_ids())
        add_ids(FinishedJobRegistry(queue=self._queue).get_job_ids())
        add_ids(FailedJobRegistry(queue=self._queue).get_job_ids())
        add_ids(DeferredJobRegistry(queue=self._queue).get_job_ids())
        add_ids(ScheduledJobRegistry(queue=self._queue).get_job_ids())

        jobs = []
        for job_id in job_ids:
            try:
                jobs.append(Job.fetch(job_id, connection=connection))
            except Exception:
                continue

        return jobs