from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.models.job_status import JobStatus
from app.services.job_service import CREATE_FUNC_PATH, JobService, UPDATE_FUNC_PATH


class FakeJob:
    def __init__(self, job_id="job-1", status="queued", *, meta=None, created_at=None, started_at=None, ended_at=None, exc_info=None):
        self.id = job_id
        self._status = status
        self.meta = meta or {}
        self.created_at = created_at
        self.started_at = started_at
        self.ended_at = ended_at
        self.exc_info = exc_info
        self.saved = False

    def get_status(self):
        return self._status

    def save_meta(self):
        self.saved = True


class FakeRepo:
    def __init__(self, job=None):
        self.job = job or FakeJob()
        self.enqueued = []
        self.deleted = []

    def enqueue(self, func_path, **kwargs):
        new_job = FakeJob(job_id="replacement", status="queued", meta={})
        self.enqueued.append((func_path, kwargs, new_job))
        return new_job

    def get_job(self, job_id):
        return self.job

    def get_all_jobs(self):
        return [self.job]

    def delete_job(self, job_id):
        self.deleted.append(job_id)


class FakeCleanup:
    def __init__(self):
        self.calls = []

    def cleanup_failed_job_artifacts(self, metadata):
        self.calls.append(metadata)


def test_enqueue_create_sets_metadata():
    repo = FakeRepo()
    service = JobService(repo)
    response = service.enqueue_create({"output_name": "Movie"})
    func_path, kwargs, job = repo.enqueued[0]
    assert response.job_id == "replacement"
    assert func_path == CREATE_FUNC_PATH
    assert kwargs["request_payload"] == {"output_name": "Movie"}
    assert job.meta["job_type"] == "create"
    assert job.meta["work_dir_name"] == "job-replacement"
    assert job.saved is True


def test_enqueue_update_uses_update_path_without_workdir():
    repo = FakeRepo()
    service = JobService(repo)
    service.enqueue_update({"output_name": "Movie"})
    _, _, job = repo.enqueued[0]
    assert job.meta["func_path"] == UPDATE_FUNC_PATH
    assert job.meta["job_type"] == "update"
    assert job.meta["work_dir_name"] is None


def test_retry_job_cleans_up_and_tracks_source_job():
    failed_job = FakeJob(
        job_id="orig",
        status="failed",
        meta={"job_type": "create", "request_payload": {"output_name": "Movie"}, "func_path": CREATE_FUNC_PATH},
    )
    repo = FakeRepo(job=failed_job)
    cleanup = FakeCleanup()
    response = JobService(repo).retry_job("orig", cleanup)
    assert response.job_id == "replacement"
    assert cleanup.calls[0]["job_id"] == "orig"
    replacement = repo.enqueued[0][2]
    assert replacement.meta["retried_from_job_id"] == "orig"
    assert replacement.saved is True


@pytest.mark.parametrize("status", [JobStatus.STARTED.value, JobStatus.QUEUED.value, JobStatus.FINISHED.value])
def test_retry_rejects_nonrecoverable_statuses(status):
    repo = FakeRepo(job=FakeJob(job_id="orig", status=status))
    with pytest.raises(ValueError):
        JobService(repo).retry_job("orig", FakeCleanup())


def test_delete_job_runs_cleanup_then_deletes():
    repo = FakeRepo(
        job=FakeJob(job_id="orig", status="stopped", meta={"job_type": "update", "request_payload": {"output_name": "Movie"}})
    )
    cleanup = FakeCleanup()
    JobService(repo).delete_job("orig", cleanup)
    assert cleanup.calls[0]["job_type"] == "update"
    assert repo.deleted == ["orig"]


@pytest.mark.parametrize(
    ("started_delta", "ended_delta", "expected"),
    [(-90, None, 90), (-120, -60, 60)],
)
def test_to_job_response_duration_calculation(started_delta, ended_delta, expected):
    now = datetime.now(timezone.utc)
    job = FakeJob(
        status="started",
        meta={"output_name": "Movie"},
        started_at=now + timedelta(seconds=started_delta),
        ended_at=(now + timedelta(seconds=ended_delta)) if ended_delta is not None else None,
    )
    response = JobService(FakeRepo(job=job)).get_status("job-1")
    assert response.duration_seconds in {expected, expected - 1, expected + 1}


def test_build_error_summary_uses_last_meaningful_line():
    service = JobService(FakeRepo())
    summary = service._build_error_summary("Traceback\n  File 'x'\nValueError: boom\n")
    assert summary == "ValueError: boom"
