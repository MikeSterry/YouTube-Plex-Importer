"""Canonical job status values and helpers."""

from enum import Enum


class JobStatus(str, Enum):
    """Canonical background job statuses."""

    QUEUED = "queued"
    DEFERRED = "deferred"
    STARTED = "started"
    SCHEDULED = "scheduled"
    FINISHED = "finished"
    FAILED = "failed"
    STOPPED = "stopped"
    CANCELED = "canceled"
    UNKNOWN = "unknown"

    @classmethod
    def from_value(cls, value: str | None) -> "JobStatus":
        """Safely convert an external status string to JobStatus."""
        if not value:
            return cls.UNKNOWN

        normalized = value.strip().lower()
        for status in cls:
            if status.value == normalized:
                return status
        return cls.UNKNOWN

    @property
    def is_active(self) -> bool:
        """Return whether this status is actively processing."""
        return self in {
            JobStatus.QUEUED,
            JobStatus.DEFERRED,
            JobStatus.STARTED,
            JobStatus.SCHEDULED,
        }

    @property
    def is_terminal(self) -> bool:
        """Return whether this status is finished and no longer running."""
        return self in {
            JobStatus.FINISHED,
            JobStatus.FAILED,
            JobStatus.STOPPED,
            JobStatus.CANCELED,
        }

    @property
    def group_name(self) -> str:
        """Return a UI group label."""
        if self.is_active:
            return "Processing"
        if self == JobStatus.FINISHED:
            return "Completed"
        if self in {JobStatus.FAILED, JobStatus.STOPPED, JobStatus.CANCELED}:
            return "Issues"
        return "Other"

    @property
    def css_class(self) -> str:
        """Return the CSS class used for this status."""
        mapping = {
            JobStatus.QUEUED: "status-queued",
            JobStatus.DEFERRED: "status-deferred",
            JobStatus.STARTED: "status-started",
            JobStatus.SCHEDULED: "status-scheduled",
            JobStatus.FINISHED: "status-finished",
            JobStatus.FAILED: "status-failed",
            JobStatus.STOPPED: "status-stopped",
            JobStatus.CANCELED: "status-canceled",
            JobStatus.UNKNOWN: "status-unknown",
        }
        return mapping[self]