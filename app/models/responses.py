"""Response DTOs."""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.job_status import JobStatus


@dataclass(frozen=True)
class JobResponse:
    """Background job metadata."""

    job_id: str
    status: str
    output_name: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None

    @property
    def status_enum(self) -> JobStatus:
        """Return the canonical status enum."""
        return JobStatus.from_value(self.status)

    @property
    def duration_display(self) -> str:
        """Return a human-friendly duration string."""
        if self.duration_seconds is None:
            return "-"

        total = self.duration_seconds
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours:
            return f"{hours}h {minutes}m {seconds}s"
        if minutes:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"

    @property
    def status_css_class(self) -> str:
        """Return the CSS class used to style this status."""
        return self.status_enum.css_class

    def to_dict(self) -> Dict[str, Any]:
        """Convert the response to a serializable dict."""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "output_name": self.output_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": self.duration_seconds,
            "duration_display": self.duration_display,
            "status_css_class": self.status_css_class,
            "group_name": self.status_enum.group_name,
        }


@dataclass(frozen=True)
class JobStatusListResponse:
    """Collection of background jobs for status UI/API."""

    jobs: List[JobResponse]

    def to_dict(self) -> Dict[str, Any]:
        """Convert the response to a serializable dict."""
        return {
            "jobs": [job.to_dict() for job in self.jobs]
        }


@dataclass(frozen=True)
class OutputEntry:
    """Output folder summary used by the UI and API."""

    name: str
    path: str
    files: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert the response to a serializable dict."""
        return asdict(self)