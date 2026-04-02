"""Helpers for sorting, filtering, and grouping jobs."""

from dataclasses import dataclass
from typing import Iterable

from app.models.job_status import JobStatus
from app.models.responses import JobResponse


_STATUS_SORT_ORDER = {
    JobStatus.STARTED: 0,
    JobStatus.QUEUED: 1,
    JobStatus.DEFERRED: 2,
    JobStatus.SCHEDULED: 3,
    JobStatus.FINISHED: 4,
    JobStatus.FAILED: 5,
    JobStatus.STOPPED: 6,
    JobStatus.CANCELED: 7,
    JobStatus.UNKNOWN: 99,
}


@dataclass(frozen=True)
class JobGroup:
    """A visual group of jobs for the status page."""

    name: str
    jobs: list[JobResponse]


@dataclass(frozen=True)
class JobCollection:
    """Collection wrapper for sorting, filtering, and grouping jobs."""

    jobs: list[JobResponse]

    @classmethod
    def from_iterable(cls, jobs: Iterable[JobResponse]) -> "JobCollection":
        """Build a collection from an iterable."""
        return cls(list(jobs))

    def sorted(self) -> "JobCollection":
        """Return jobs sorted by status priority and recency."""
        sorted_jobs = sorted(
            self.jobs,
            key=lambda job: (
                _STATUS_SORT_ORDER.get(job.status_enum, 99),
                0 if job.started_at else 1,
                -(job.started_at.timestamp()) if job.started_at else 0,
                -(job.created_at.timestamp()) if job.created_at else 0,
                (job.output_name or "").lower(),
                job.job_id,
            ),
        )
        return JobCollection(sorted_jobs)

    def filter_active_only(self) -> "JobCollection":
        """Return only jobs that are actively processing."""
        return JobCollection([job for job in self.jobs if job.status_enum.is_active])

    def filter_by_group(self, group: str | None) -> "JobCollection":
        """Return jobs matching a UI group."""
        if not group:
            return self

        normalized = group.strip().lower()
        if normalized == "processing":
            return JobCollection([job for job in self.jobs if job.status_enum.group_name == "Processing"])
        if normalized == "completed":
            return JobCollection([job for job in self.jobs if job.status_enum.group_name == "Completed"])
        if normalized == "issues":
            return JobCollection([job for job in self.jobs if job.status_enum.group_name == "Issues"])
        if normalized == "all":
            return self
        return self

    def grouped(self) -> list[JobGroup]:
        """Return grouped jobs for visual rendering."""
        sections = ["Processing", "Completed", "Issues", "Other"]
        groups: list[JobGroup] = []

        for section in sections:
            section_jobs = [job for job in self.jobs if job.status_enum.group_name == section]
            if section_jobs:
                groups.append(JobGroup(name=section, jobs=section_jobs))

        return groups

    @property
    def active_count(self) -> int:
        """Count active jobs."""
        return sum(1 for job in self.jobs if job.status_enum.is_active)

    @property
    def completed_count(self) -> int:
        """Count completed jobs."""
        return sum(1 for job in self.jobs if job.status_enum == JobStatus.FINISHED)

    @property
    def issue_count(self) -> int:
        """Count jobs with issues."""
        return sum(
            1
            for job in self.jobs
            if job.status_enum in {JobStatus.FAILED, JobStatus.STOPPED, JobStatus.CANCELED}
        )