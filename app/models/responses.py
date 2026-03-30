"""Response DTOs."""

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class JobResponse:
    """Background job metadata."""

    job_id: str
    status: str
    output_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the response to a serializable dict."""
        return asdict(self)


@dataclass(frozen=True)
class OutputEntry:
    """Output folder summary used by the UI and API."""

    name: str
    path: str
    files: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert the response to a serializable dict."""
        return asdict(self)
