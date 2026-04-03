from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask

from app.controllers.api_controller import api_blueprint
from app.exceptions import AppError


class DummyResponse:
    def __init__(self, **kwargs):
        self.payload = kwargs

    def to_dict(self):
        return dict(self.payload)


class DummyRequestHandler:
    def submit_create(self, model):
        return DummyResponse(
            job_id="job-create-123",
            status="queued",
            status_css_class="status-queued",
            output_name=model.output_name or "Created Output",
            created_at="2026-04-02T19:34:31",
            started_at="-",
            finished_at="-",
            duration_display="-",
        )

    def submit_update(self, model):
        return DummyResponse(
            job_id="job-update-123",
            status="queued",
            status_css_class="status-queued",
            output_name=model.output_name,
            created_at="2026-04-02T19:34:31",
            started_at="-",
            finished_at="-",
            duration_display="-",
        )


class DummyOutputRepository:
    def list_outputs(self):
        return []

    def list_poster_files(self, output_name):
        return [f"{output_name}-poster.jpg"]

    def resolve_poster_file(self, output_name, file_name):
        return f"/tmp/{output_name}/{file_name}"


class DummyJobService:
    def get_status(self, job_id):
        return DummyResponse(
            job_id=job_id,
            status="started",
            status_css_class="status-started",
            output_name="Laid to Rest",
            created_at="2026-04-02T19:34:31.360638",
            started_at="2026-04-02T19:34:31.384906",
            finished_at="-",
            duration_display="15s",
        )


class DummyImageService:
    def fetch_source_bytes(self, image_url):
        return b"image-bytes", "image/jpeg"

    def fetch_local_source_bytes(self, poster_path):
        return b"local-image-bytes", "image/jpeg"

    def build_poster_preview_bytes(self, image_url, crop_settings):
        return b"preview-bytes"

    def build_local_poster_preview_bytes(self, poster_path, crop_settings):
        return b"local-preview-bytes"


@pytest.fixture()
def client():
    app = Flask(__name__)
    app.testing = True
    app.config["APP_CONTAINER"] = SimpleNamespace(
        request_handler=DummyRequestHandler(),
        output_repository=DummyOutputRepository(),
        job_service=DummyJobService(),
        image_service=DummyImageService(),
    )

    @app.errorhandler(AppError)
    def handle_app_error(error):
        payload = error.to_payload()
        return payload.to_dict(), payload.status_code

    app.register_blueprint(api_blueprint)
    return app.test_client(), app.config["APP_CONTAINER"]


@pytest.mark.parametrize(
    ("payload", "field_name"),
    [
        ({}, "youtube_url"),
        ({"youtube_url": ""}, "youtube_url"),
        ({"youtube_url": "   "}, "youtube_url"),
    ],
)
def test_create_request_requires_youtube_url(client, payload, field_name):
    test_client, _ = client

    response = test_client.post("/api/v1/requests", json=payload)

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == f"{field_name} is required"
    assert body["code"] == "missing_field"
    assert body["details"]["field"] == field_name


@pytest.mark.parametrize(
    ("payload", "field_name"),
    [
        ({}, "output_name"),
        ({"output_name": ""}, "output_name"),
        ({"output_name": "   "}, "output_name"),
    ],
)
def test_update_request_requires_output_name(client, payload, field_name):
    test_client, _ = client

    response = test_client.post("/api/v1/updates", json=payload)

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == f"{field_name} is required"
    assert body["code"] == "missing_field"
    assert body["details"]["field"] == field_name


@pytest.mark.parametrize(
    ("payload", "field_name"),
    [
        (
            {
                "youtube_url": "https://youtu.be/example",
                "poster_url": "https://image.tmdb.org/poster.jpg",
                "poster_zoom": "abc",
            },
            "poster_zoom",
        ),
        (
            {
                "youtube_url": "https://youtu.be/example",
                "poster_url": "https://image.tmdb.org/poster.jpg",
                "poster_offset_x": "abc",
            },
            "poster_offset_x",
        ),
        (
            {
                "youtube_url": "https://youtu.be/example",
                "poster_url": "https://image.tmdb.org/poster.jpg",
                "poster_offset_y": "abc",
            },
            "poster_offset_y",
        ),
    ],
)
def test_create_request_rejects_invalid_poster_float_fields(client, payload, field_name):
    test_client, _ = client

    response = test_client.post("/api/v1/requests", json=payload)

    assert response.status_code == 400
    body = response.get_json()
    assert body["code"] == "invalid_field"
    assert body["details"]["field"] == field_name


@pytest.mark.parametrize(
    ("query_string", "field_name"),
    [
        ("&zoom=bad", "zoom"),
        ("&offset_x=bad", "offset_x"),
        ("&offset_y=bad", "offset_y"),
    ],
)
def test_poster_preview_rejects_invalid_query_floats(client, query_string, field_name):
    test_client, _ = client

    response = test_client.get(f"/api/v1/artwork/poster-preview?url=https://image.test/poster.jpg{query_string}")

    assert response.status_code == 400
    body = response.get_json()
    assert body["code"] == "invalid_field"
    assert body["details"]["field"] == field_name


def test_job_status_and_artwork_routes(client):
    test_client, _ = client

    job = test_client.get("/api/v1/jobs/job-123")
    assert job.status_code == 200
    assert job.get_json()["job_id"] == "job-123"

    poster_files = test_client.get("/api/v1/outputs/Test%20Movie/poster-files")
    assert poster_files.status_code == 200
    assert poster_files.get_json()["output_name"] == "Test Movie"

    local_source = test_client.get("/api/v1/artwork/local-source?output_name=Test%20Movie&file=poster.jpg")
    assert local_source.status_code == 200
    assert local_source.mimetype == "image/jpeg"

    local_preview = test_client.get(
        "/api/v1/artwork/local-poster-preview"
        "?output_name=Test%20Movie&file=poster.jpg&zoom=1.2&offset_x=0.4&offset_y=0.7"
    )
    assert local_preview.status_code == 200
    assert local_preview.mimetype == "image/jpeg"


def test_create_request_success(client):
    test_client, _ = client

    response = test_client.post(
        "/api/v1/requests",
        json={"youtube_url": "https://youtu.be/example"},
    )

    assert response.status_code == 202
    body = response.get_json()
    assert body["job_id"] == "job-create-123"


def test_update_request_success(client):
    test_client, _ = client

    response = test_client.post(
        "/api/v1/updates",
        json={"output_name": "Laid to Rest"},
    )

    assert response.status_code == 202
    body = response.get_json()
    assert body["job_id"] == "job-update-123"