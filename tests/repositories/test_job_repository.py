from __future__ import annotations

import pytest

import app.repositories.job_repository as job_repository_module
from app.repositories.job_repository import JobRepository


class DummyQueue:
    def __init__(self):
        self.connection = object()
        self.job_ids = ["queued-1", "dup-1"]
        self.enqueue_calls = []

    def enqueue(self, func_path, **kwargs):
        self.enqueue_calls.append((func_path, kwargs))
        return {"job_id": "enqueued-123", "func_path": func_path, "kwargs": kwargs}


class DummyRegistry:
    def __init__(self, ids=None, remove_exception=None):
        self._ids = ids or []
        self.remove_calls = []
        self.remove_exception = remove_exception

    def get_job_ids(self):
        return list(self._ids)

    def remove(self, job_id, delete_job=False):
        self.remove_calls.append((job_id, delete_job))
        if self.remove_exception:
            raise self.remove_exception


class DummyJob:
    def __init__(self, job_id):
        self.id = job_id
        self.delete_calls = 0

    def delete(self):
        self.delete_calls += 1


@pytest.fixture()
def queue():
    return DummyQueue()


@pytest.fixture()
def repository(queue):
    return JobRepository(queue)


# ---------------------------
# enqueue
# ---------------------------

def test_enqueue_delegates_to_queue(repository, queue):
    result = repository.enqueue(
        "app.handlers.background_jobs.process_create_request",
        foo="bar",
        answer=42,
    )

    assert queue.enqueue_calls == [
        (
            "app.handlers.background_jobs.process_create_request",
            {"foo": "bar", "answer": 42},
        )
    ]
    assert result == {
        "job_id": "enqueued-123",
        "func_path": "app.handlers.background_jobs.process_create_request",
        "kwargs": {"foo": "bar", "answer": 42},
    }


# ---------------------------
# get_job
# ---------------------------

def test_get_job_fetches_from_rq_with_queue_connection(repository, queue, monkeypatch):
    fetch_calls = []
    fetched_job = DummyJob("job-123")

    monkeypatch.setattr(
        job_repository_module.Job,
        "fetch",
        lambda job_id, connection: fetch_calls.append((job_id, connection)) or fetched_job,
    )

    result = repository.get_job("job-123")

    assert result is fetched_job
    assert fetch_calls == [("job-123", queue.connection)]


# ---------------------------
# get_all_jobs
# ---------------------------

def test_get_all_jobs_collects_unique_jobs_across_sources(repository, queue, monkeypatch):
    started_registry = DummyRegistry(["started-1", "dup-1"])
    finished_registry = DummyRegistry(["finished-1"])
    failed_registry = DummyRegistry(["failed-1", "queued-1"])
    deferred_registry = DummyRegistry(["deferred-1"])
    scheduled_registry = DummyRegistry(["scheduled-1"])

    monkeypatch.setattr(job_repository_module, "StartedJobRegistry", lambda queue: started_registry)
    monkeypatch.setattr(job_repository_module, "FinishedJobRegistry", lambda queue: finished_registry)
    monkeypatch.setattr(job_repository_module, "FailedJobRegistry", lambda queue: failed_registry)
    monkeypatch.setattr(job_repository_module, "DeferredJobRegistry", lambda queue: deferred_registry)
    monkeypatch.setattr(job_repository_module, "ScheduledJobRegistry", lambda queue: scheduled_registry)

    fetch_calls = []

    def fake_fetch(job_id, connection):
        fetch_calls.append((job_id, connection))
        return DummyJob(job_id)

    monkeypatch.setattr(job_repository_module.Job, "fetch", fake_fetch)

    result = repository.get_all_jobs()

    assert [job.id for job in result] == [
        "queued-1",
        "dup-1",
        "started-1",
        "finished-1",
        "failed-1",
        "deferred-1",
        "scheduled-1",
    ]

    assert fetch_calls == [
        ("queued-1", queue.connection),
        ("dup-1", queue.connection),
        ("started-1", queue.connection),
        ("finished-1", queue.connection),
        ("failed-1", queue.connection),
        ("deferred-1", queue.connection),
        ("scheduled-1", queue.connection),
    ]


def test_get_all_jobs_skips_failed_fetches(repository, monkeypatch):
    queue = repository._queue
    queue.job_ids = ["good-1", "bad-1", "good-2"]

    monkeypatch.setattr(job_repository_module, "StartedJobRegistry", lambda queue: DummyRegistry([]))
    monkeypatch.setattr(job_repository_module, "FinishedJobRegistry", lambda queue: DummyRegistry([]))
    monkeypatch.setattr(job_repository_module, "FailedJobRegistry", lambda queue: DummyRegistry([]))
    monkeypatch.setattr(job_repository_module, "DeferredJobRegistry", lambda queue: DummyRegistry([]))
    monkeypatch.setattr(job_repository_module, "ScheduledJobRegistry", lambda queue: DummyRegistry([]))

    def fake_fetch(job_id, connection):
        if job_id == "bad-1":
            raise RuntimeError("missing")
        return DummyJob(job_id)

    monkeypatch.setattr(job_repository_module.Job, "fetch", fake_fetch)

    result = repository.get_all_jobs()

    assert [job.id for job in result] == ["good-1", "good-2"]


# ---------------------------
# delete_job
# ---------------------------

def test_delete_job_removes_from_registries_and_deletes_job(repository, queue, monkeypatch):
    registries = [DummyRegistry() for _ in range(5)]

    monkeypatch.setattr(job_repository_module, "StartedJobRegistry", lambda queue: registries[0])
    monkeypatch.setattr(job_repository_module, "FinishedJobRegistry", lambda queue: registries[1])
    monkeypatch.setattr(job_repository_module, "FailedJobRegistry", lambda queue: registries[2])
    monkeypatch.setattr(job_repository_module, "DeferredJobRegistry", lambda queue: registries[3])
    monkeypatch.setattr(job_repository_module, "ScheduledJobRegistry", lambda queue: registries[4])

    job = DummyJob("job-123")

    monkeypatch.setattr(
        job_repository_module.Job,
        "fetch",
        lambda job_id, connection: job,
    )

    repository.delete_job("job-123")

    for registry in registries:
        assert registry.remove_calls == [("job-123", False)]

    assert job.delete_calls == 1


def test_delete_job_ignores_registry_errors(repository, monkeypatch):
    registries = [DummyRegistry(remove_exception=RuntimeError("boom")) for _ in range(5)]

    monkeypatch.setattr(job_repository_module, "StartedJobRegistry", lambda queue: registries[0])
    monkeypatch.setattr(job_repository_module, "FinishedJobRegistry", lambda queue: registries[1])
    monkeypatch.setattr(job_repository_module, "FailedJobRegistry", lambda queue: registries[2])
    monkeypatch.setattr(job_repository_module, "DeferredJobRegistry", lambda queue: registries[3])
    monkeypatch.setattr(job_repository_module, "ScheduledJobRegistry", lambda queue: registries[4])

    job = DummyJob("job-123")
    monkeypatch.setattr(job_repository_module.Job, "fetch", lambda job_id, connection: job)

    repository.delete_job("job-123")

    assert job.delete_calls == 1


def test_delete_job_returns_when_fetch_fails(repository, monkeypatch):
    registries = [DummyRegistry() for _ in range(5)]

    monkeypatch.setattr(job_repository_module, "StartedJobRegistry", lambda queue: registries[0])
    monkeypatch.setattr(job_repository_module, "FinishedJobRegistry", lambda queue: registries[1])
    monkeypatch.setattr(job_repository_module, "FailedJobRegistry", lambda queue: registries[2])
    monkeypatch.setattr(job_repository_module, "DeferredJobRegistry", lambda queue: registries[3])
    monkeypatch.setattr(job_repository_module, "ScheduledJobRegistry", lambda queue: registries[4])

    monkeypatch.setattr(
        job_repository_module.Job,
        "fetch",
        lambda job_id, connection: (_ for _ in ()).throw(RuntimeError("fetch failed")),
    )

    repository.delete_job("job-123")

    for registry in registries:
        assert registry.remove_calls == [("job-123", False)]


def test_delete_job_ignores_delete_failures(repository, monkeypatch):
    monkeypatch.setattr(job_repository_module, "StartedJobRegistry", lambda queue: DummyRegistry())
    monkeypatch.setattr(job_repository_module, "FinishedJobRegistry", lambda queue: DummyRegistry())
    monkeypatch.setattr(job_repository_module, "FailedJobRegistry", lambda queue: DummyRegistry())
    monkeypatch.setattr(job_repository_module, "DeferredJobRegistry", lambda queue: DummyRegistry())
    monkeypatch.setattr(job_repository_module, "ScheduledJobRegistry", lambda queue: DummyRegistry())

    class BadJob:
        def delete(self):
            raise RuntimeError("delete failed")

    monkeypatch.setattr(job_repository_module.Job, "fetch", lambda job_id, connection: BadJob())

    repository.delete_job("job-123")