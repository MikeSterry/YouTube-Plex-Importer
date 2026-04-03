from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.handlers.background_jobs as background_jobs
from app.models.domain import PosterCropSettings


class DummyJob:
    def __init__(self, job_id: str = "job-123"):
        self.id = job_id
        self.meta = {}
        self.save_meta_calls = 0

    def save_meta(self) -> None:
        self.save_meta_calls += 1


class DummyRequestHandler:
    def __init__(self):
        self.create_calls = []
        self.update_calls = []
        self.create_result = {"output_name": "Created Output", "status": "finished"}
        self.update_result = {"output_name": "Updated Output", "status": "finished"}
        self.raise_on_create = None
        self.raise_on_update = None

    def process_create(self, request_model):
        self.create_calls.append(request_model)
        if self.raise_on_create:
            raise self.raise_on_create
        return dict(self.create_result)

    def process_update(self, request_model):
        self.update_calls.append(request_model)
        if self.raise_on_update:
            raise self.raise_on_update
        return dict(self.update_result)


@pytest.fixture()
def harness(monkeypatch):
    job = DummyJob()
    request_handler = DummyRequestHandler()
    container = SimpleNamespace(request_handler=request_handler)

    set_job_id_calls = []
    clear_job_id_calls = []

    monkeypatch.setattr(background_jobs, "get_current_job", lambda: job)
    monkeypatch.setattr(background_jobs, "build_container", lambda: container)
    monkeypatch.setattr(background_jobs, "set_job_id", lambda value: set_job_id_calls.append(value))
    monkeypatch.setattr(background_jobs, "clear_job_id", lambda: clear_job_id_calls.append(True))

    return SimpleNamespace(
        job=job,
        request_handler=request_handler,
        container=container,
        set_job_id_calls=set_job_id_calls,
        clear_job_id_calls=clear_job_id_calls,
    )


def test_inflate_payload_returns_plain_payload_when_no_crop_settings():
    payload = {
        "youtube_url": "https://youtu.be/example",
        "output_name": "Test Output",
    }

    result = background_jobs._inflate_payload(payload)

    assert result == payload
    assert result is not payload


def test_inflate_payload_converts_crop_settings_dict_to_domain_object():
    payload = {
        "youtube_url": "https://youtu.be/example",
        "poster_crop_settings": {
            "zoom": 1.25,
            "offset_x": 0.4,
            "offset_y": 0.6,
            "mode": "cover",
        },
    }

    result = background_jobs._inflate_payload(payload)

    assert isinstance(result["poster_crop_settings"], PosterCropSettings)
    assert result["poster_crop_settings"].zoom == 1.25
    assert result["poster_crop_settings"].offset_x == 0.4
    assert result["poster_crop_settings"].offset_y == 0.6
    assert result["poster_crop_settings"].mode == "cover"


def test_process_create_request_happy_path_sets_job_metadata_and_returns_result(harness):
    payload = {
        "youtube_url": "https://youtu.be/example",
        "output_name": "Requested Output",
        "poster_crop_settings": {
            "zoom": 1.1,
            "offset_x": 0.2,
            "offset_y": 0.8,
            "mode": "contain",
        },
    }

    result = background_jobs.process_create_request(payload)

    assert result == {"output_name": "Created Output", "status": "finished"}
    assert harness.set_job_id_calls == ["job-123"]
    assert harness.clear_job_id_calls == [True]
    assert harness.job.meta["output_name"] == "Created Output"
    assert harness.job.save_meta_calls == 1

    assert len(harness.request_handler.create_calls) == 1
    request_model = harness.request_handler.create_calls[0]
    assert request_model.youtube_url == "https://youtu.be/example"
    assert request_model.output_name == "Requested Output"
    assert isinstance(request_model.poster_crop_settings, PosterCropSettings)
    assert request_model.poster_crop_settings.mode == "contain"


def test_process_update_request_happy_path_sets_job_metadata_and_returns_result(harness):
    payload = {
        "output_name": "Existing Output",
        "poster_url": "https://image.test/poster.jpg",
        "poster_crop_settings": {
            "zoom": 1.3,
            "offset_x": 0.5,
            "offset_y": 0.7,
            "mode": "cover",
        },
    }

    result = background_jobs.process_update_request(payload)

    assert result == {"output_name": "Updated Output", "status": "finished"}
    assert harness.set_job_id_calls == ["job-123"]
    assert harness.clear_job_id_calls == [True]
    assert harness.job.meta["output_name"] == "Updated Output"
    assert harness.job.save_meta_calls == 1

    assert len(harness.request_handler.update_calls) == 1
    request_model = harness.request_handler.update_calls[0]
    assert request_model.output_name == "Existing Output"
    assert request_model.poster_url == "https://image.test/poster.jpg"
    assert isinstance(request_model.poster_crop_settings, PosterCropSettings)
    assert request_model.poster_crop_settings.zoom == 1.3


def test_process_create_request_uses_dash_when_no_current_job(monkeypatch):
    request_handler = DummyRequestHandler()
    container = SimpleNamespace(request_handler=request_handler)
    set_job_id_calls = []
    clear_job_id_calls = []

    monkeypatch.setattr(background_jobs, "get_current_job", lambda: None)
    monkeypatch.setattr(background_jobs, "build_container", lambda: container)
    monkeypatch.setattr(background_jobs, "set_job_id", lambda value: set_job_id_calls.append(value))
    monkeypatch.setattr(background_jobs, "clear_job_id", lambda: clear_job_id_calls.append(True))

    result = background_jobs.process_create_request(
        {"youtube_url": "https://youtu.be/example"}
    )

    assert result == {"output_name": "Created Output", "status": "finished"}
    assert set_job_id_calls == ["-"]
    assert clear_job_id_calls == [True]


def test_process_update_request_uses_dash_when_no_current_job(monkeypatch):
    request_handler = DummyRequestHandler()
    container = SimpleNamespace(request_handler=request_handler)
    set_job_id_calls = []
    clear_job_id_calls = []

    monkeypatch.setattr(background_jobs, "get_current_job", lambda: None)
    monkeypatch.setattr(background_jobs, "build_container", lambda: container)
    monkeypatch.setattr(background_jobs, "set_job_id", lambda value: set_job_id_calls.append(value))
    monkeypatch.setattr(background_jobs, "clear_job_id", lambda: clear_job_id_calls.append(True))

    result = background_jobs.process_update_request(
        {"output_name": "Existing Output"}
    )

    assert result == {"output_name": "Updated Output", "status": "finished"}
    assert set_job_id_calls == ["-"]
    assert clear_job_id_calls == [True]


def test_process_create_request_clears_job_id_on_failure(harness):
    harness.request_handler.raise_on_create = RuntimeError("create failed")

    with pytest.raises(RuntimeError, match="create failed"):
        background_jobs.process_create_request(
            {"youtube_url": "https://youtu.be/example"}
        )

    assert harness.set_job_id_calls == ["job-123"]
    assert harness.clear_job_id_calls == [True]
    assert harness.job.save_meta_calls == 0
    assert harness.job.meta == {}


def test_process_update_request_clears_job_id_on_failure(harness):
    harness.request_handler.raise_on_update = RuntimeError("update failed")

    with pytest.raises(RuntimeError, match="update failed"):
        background_jobs.process_update_request(
            {"output_name": "Existing Output"}
        )

    assert harness.set_job_id_calls == ["job-123"]
    assert harness.clear_job_id_calls == [True]
    assert harness.job.save_meta_calls == 0
    assert harness.job.meta == {}


def test_process_create_request_saves_none_output_name_when_handler_returns_none(harness):
    harness.request_handler.create_result = {"output_name": None, "status": "finished"}

    result = background_jobs.process_create_request(
        {"youtube_url": "https://youtu.be/example"}
    )

    assert result["output_name"] is None
    assert "output_name" in harness.job.meta
    assert harness.job.meta["output_name"] is None
    assert harness.job.save_meta_calls == 1


def test_process_update_request_saves_none_output_name_when_handler_returns_none(harness):
    harness.request_handler.update_result = {"output_name": None, "status": "finished"}

    result = background_jobs.process_update_request(
        {"output_name": "Existing Output"}
    )

    assert result["output_name"] is None
    assert "output_name" in harness.job.meta
    assert harness.job.meta["output_name"] is None
    assert harness.job.save_meta_calls == 1