from __future__ import annotations

import inspect
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services.job_service import JobService


class DummyRepository:
    def __init__(self, jobs=None):
        self.jobs = jobs or {}
        self.get_job_calls = []
        self.get_all_jobs_calls = 0

    def get_job(self, job_id):
        self.get_job_calls.append(job_id)
        return self.jobs.get(job_id)

    def get_all_jobs(self):
        self.get_all_jobs_calls += 1
        return list(self.jobs.values())


class DummyJob:
    def __init__(
        self,
        job_id,
        status="queued",
        output_name="Movie One",
        created_at=None,
        started_at=None,
        finished_at=None,
        error_message=None,
    ):
        self.id = job_id
        self.meta = {
            "output_name": output_name,
            "status": status,
        }
        self.created_at = created_at
        self.enqueued_at = created_at
        self.started_at = started_at
        self.ended_at = finished_at
        self.exc_info = error_message



@dataclass(frozen=True)
class DummyStatusEnum:
    value: str
    is_active: bool
    group_name: str


def _status_enum(status: str):
    normalized = (status or "queued").strip().lower()
    is_active = normalized in {"queued", "started"}
    if normalized in {"queued", "started"}:
        group_name = "Processing"
    elif normalized == "finished":
        group_name = "Completed"
    elif normalized in {"failed", "canceled", "stopped"}:
        group_name = "Issues"
    else:
        group_name = "Other"

    return DummyStatusEnum(
        value=normalized,
        is_active=is_active,
        group_name=group_name,
    )


@pytest.fixture()
def now():
    return datetime(2026, 4, 3, 14, 0, 0)


@pytest.fixture()
def jobs(now):
    return {
        "job-queued": DummyJob("job-queued", status="queued", created_at=now),
        "job-started": DummyJob(
            "job-started",
            status="started",
            created_at=now,
            started_at=now + timedelta(seconds=5),
        ),
        "job-finished": DummyJob(
            "job-finished",
            status="finished",
            created_at=now,
            started_at=now + timedelta(seconds=5),
            finished_at=now + timedelta(seconds=65),
        ),
        "job-failed": DummyJob(
            "job-failed",
            status="failed",
            created_at=now,
            started_at=now + timedelta(seconds=10),
            finished_at=now + timedelta(seconds=20),
            error_message="yt-dlp failed",
        ),
        "job-canceled": DummyJob(
            "job-canceled",
            status="canceled",
            created_at=now,
            finished_at=now + timedelta(seconds=20),
            error_message="Canceled by user",
        ),
        "job-stopped": DummyJob(
            "job-stopped",
            status="stopped",
            created_at=now,
            finished_at=now + timedelta(seconds=25),
            error_message="Worker died",
        ),
    }


@pytest.fixture()
def repository(jobs):
    return DummyRepository(jobs=jobs)


@pytest.fixture()
def service(repository, monkeypatch):
    signature = inspect.signature(JobService)
    kwargs = {}

    for name in signature.parameters:
        if name == "self":
            continue
        if name in {"job_repository", "repository", "job_repo"}:
            kwargs[name] = repository
        else:
            kwargs[name] = SimpleNamespace()

    instance = JobService(**kwargs)

    for attr_name in [
        "_job_repository",
        "job_repository",
        "_repository",
        "repository",
        "_job_repo",
        "job_repo",
    ]:
        if hasattr(instance, attr_name):
            setattr(instance, attr_name, repository)

    if not any(
        hasattr(instance, attr_name)
        for attr_name in [
            "_job_repository",
            "job_repository",
            "_repository",
            "repository",
            "_job_repo",
            "job_repo",
        ]
    ):
        setattr(instance, "_job_repository", repository)

    original_to_job_response = getattr(instance, "_to_job_response", None) or getattr(instance, "to_job_response", None)

    def fake_to_job_response(job):
        if original_to_job_response is not None and job is None:
            return original_to_job_response(job)

        created_at = job.created_at or job.enqueued_at
        started_at = job.started_at
        finished_at = job.ended_at
        status = job.meta.get("status", "queued")
        duration = "-"
        if started_at and finished_at:
            duration = f"{int((finished_at - started_at).total_seconds())}s"

        return SimpleNamespace(
            job_id=job.id,
            status=status,
            status_enum=_status_enum(status),
            status_css_class=f"status-{status}",
            output_name=job.meta.get("output_name"),
            created_at=created_at,
            started_at=started_at,
            finished_at=finished_at,
            duration_display=duration,
            error_message=job.exc_info,
            to_dict=lambda: {
                "job_id": job.id,
                "status": status,
                "status_css_class": f"status-{status}",
                "output_name": job.meta.get("output_name"),
                "created_at": created_at.isoformat() if created_at else None,
                "started_at": started_at.isoformat() if started_at else None,
                "finished_at": finished_at.isoformat() if finished_at else None,
                "duration_display": duration,
                "error_message": job.exc_info,
            },
        )

    if hasattr(instance, "_to_job_response"):
        monkeypatch.setattr(instance, "_to_job_response", fake_to_job_response)
    if hasattr(instance, "to_job_response"):
        monkeypatch.setattr(instance, "to_job_response", fake_to_job_response)

    return instance


def _repo(service):
    for attr_name in ["_job_repository", "job_repository", "_repository", "repository", "_job_repo", "job_repo"]:
        if hasattr(service, attr_name):
            value = getattr(service, attr_name)
            if hasattr(value, "get_job"):
                return value
    raise AssertionError("Unable to locate job repository on JobService instance")


def _collect_job_ids(grouped):
    actual_job_ids = set()

    if isinstance(grouped, dict):
        for _, items in grouped.items():
            for item in items:
                actual_job_ids.add(item["job_id"] if isinstance(item, dict) else item.job_id)
        return actual_job_ids

    for group in grouped:
        jobs = getattr(group, "jobs", [])
        for item in jobs:
            actual_job_ids.add(item["job_id"] if isinstance(item, dict) else item.job_id)
    return actual_job_ids


def test_get_status_returns_expected_response(service):
    repo = _repo(service)

    response = service.get_status("job-started")
    body = response.to_dict()

    assert repo.get_job_calls == ["job-started"]
    assert body["job_id"] == "job-started"
    assert body["status"] == "started"
    assert body["output_name"] == "Movie One"
    assert body["started_at"] is not None


def test_get_status_missing_job_raises_current_error(service):
    with pytest.raises(AttributeError) as exc_info:
        service.get_status("missing-job")

    assert "id" in str(exc_info.value)


@pytest.mark.parametrize(
    ("active_only", "group", "expected_job_ids"),
    [
        (True, None, {"job-queued", "job-started"}),
        (False, "completed", {"job-finished"}),
        (False, "issues", {"job-failed", "job-canceled", "job-stopped"}),
        (False, None, {"job-queued", "job-started", "job-finished", "job-failed", "job-canceled", "job-stopped"}),
    ],
)
def test_get_all_statuses_filters_jobs(service, active_only, group, expected_job_ids):
    collection = service.get_all_statuses(active_only=active_only, group=group)
    grouped = collection.grouped()
    actual_job_ids = _collect_job_ids(grouped)

    assert actual_job_ids == expected_job_ids


def test_get_all_statuses_returns_job_collection_with_jobs(service):
    collection = service.get_all_statuses(active_only=False, group=None)

    assert hasattr(collection, "jobs")
    assert len(collection.jobs) == 6


def test_get_all_statuses_grouped_returns_groups(service):
    collection = service.get_all_statuses(active_only=False, group=None)
    grouped = collection.grouped()

    assert grouped
    assert _collect_job_ids(grouped) == {
        "job-queued",
        "job-started",
        "job-finished",
        "job-failed",
        "job-canceled",
        "job-stopped",
    }