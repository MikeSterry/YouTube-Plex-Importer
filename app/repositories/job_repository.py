"""Repository wrapper around the background queue."""

from rq.job import Job


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
