# tests/repositories/test_job_repository.py
from __future__ import annotations

from types import SimpleNamespace

import pytest
from rq.exceptions import NoSuchJobError

from app.exceptions import NotFoundError
from app.repositories.job_repository import JobRepository
import app.repositories.job_repository as job_repository_module


def test_get_job_returns_job_when_found(monkeypatch):
    connection = object()
    queue = SimpleNamespace(connection=connection)
    repository = JobRepository(queue)

    fetched_job = object()

    def fake_fetch(job_id, connection):
        assert job_id == "job-123"
        assert connection is queue.connection
        return fetched_job

    monkeypatch.setattr(job_repository_module.Job, "fetch", fake_fetch)

    result = repository.get_job("job-123")

    assert result is fetched_job


def test_get_job_raises_not_found_error_when_rq_job_is_missing(monkeypatch):
    queue = SimpleNamespace(connection=object())
    repository = JobRepository(queue)

    def fake_fetch(job_id, connection):
        raise NoSuchJobError(job_id)

    monkeypatch.setattr(job_repository_module.Job, "fetch", fake_fetch)

    with pytest.raises(NotFoundError, match="Job job-404 was not found."):
        repository.get_job("job-404")