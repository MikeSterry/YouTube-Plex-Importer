from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask

from app.controllers.ui_controller import ui_blueprint
from app.exceptions import ControllerRenderError


class DummyResponse:
    def __init__(self, **kwargs):
        self.payload = kwargs

    def to_dict(self):
        return dict(self.payload)


class DummyRequestHandler:
    def __init__(self):
        self.create_calls = []
        self.update_calls = []
        self.raise_on_create = None
        self.raise_on_update = None

    def submit_create(self, model):
        self.create_calls.append(model)
        if self.raise_on_create:
            raise self.raise_on_create

        return DummyResponse(
            job_id="job-create-123",
            status="Started",
            status_css_class="status-started",
            output_name=model.output_name or "Created Output",
            created_at="2026-04-02T19:34:31.360638",
            started_at="2026-04-02T19:34:31.384906",
            finished_at="-",
            duration_display="15s",
        )

    def submit_update(self, model):
        self.update_calls.append(model)
        if self.raise_on_update:
            raise self.raise_on_update

        return DummyResponse(
            job_id="job-update-123",
            status="Started",
            status_css_class="status-started",
            output_name=model.output_name,
            created_at="2026-04-02T19:34:31.360638",
            started_at="2026-04-02T19:34:31.384906",
            finished_at="-",
            duration_display="15s",
        )


class DummyOutputRepository:
    def list_outputs(self):
        return [
            SimpleNamespace(name="Laid to Rest"),
            SimpleNamespace(name="Tour Movie"),
        ]


class DummyStatusCollection:
    def __init__(self):
        self.active_count = 2
        self.completed_count = 3
        self.issue_count = 1

    def grouped(self):
        return {
            "today": [
                {
                    "job_id": "job-123",
                    "status": "Started",
                    "status_css_class": "status-started",
                    "output_name": "Laid to Rest",
                    "created_at": "2026-04-02T19:34:31.360638",
                    "started_at": "2026-04-02T19:34:31.384906",
                    "finished_at": "-",
                    "duration_display": "15s",
                }
            ]
        }


class DummyJobService:
    def __init__(self):
        self.status_calls = []
        self.all_status_calls = []

    def get_status(self, job_id):
        self.status_calls.append(job_id)
        return DummyResponse(
            job_id=job_id,
            status="Started",
            status_css_class="status-started",
            output_name="Laid to Rest",
            created_at="2026-04-02T19:34:31.360638",
            started_at="2026-04-02T19:34:31.384906",
            finished_at="-",
            duration_display="15s",
        )

    def get_all_statuses(self, active_only=True, group=None):
        self.all_status_calls.append((active_only, group))
        return DummyStatusCollection()


class DummyJobRecoveryHandler:
    def __init__(self):
        self.retry_calls = []
        self.delete_calls = []

    def retry_job(self, job_id):
        self.retry_calls.append(job_id)

    def delete_job(self, job_id):
        self.delete_calls.append(job_id)


@pytest.fixture()
def client(tmp_path):
    app = Flask(
        __name__,
        template_folder=str(tmp_path / "templates"),
    )
    app.testing = True

    templates_dir = tmp_path / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)

    (templates_dir / "index.html").write_text(
        """
        <!doctype html>
        <html>
          <body>
            <h1>Index</h1>
            {% if result %}
              {% include "_job_result_card.html" %}
            {% endif %}
            <div id="outputs-count">{{ outputs|length }}</div>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    (templates_dir / "_job_result_card.html").write_text(
        """
        {% if result %}
        <section class="job-card {{ 'job-card-error' if result.error_message else '' }}">
          <h2>{{ 'Request Failed' if result.error_message else 'Job Submitted' }}</h2>
          <div class="job-id">{{ result.job_id }}</div>
          <div class="job-status">{{ result.status }}</div>
          {% if result.error_message %}
            <div class="job-error-banner">{{ result.error_message }}</div>
          {% endif %}
          <div class="job-output">{{ result.output_name }}</div>
        </section>
        {% endif %}
        """,
        encoding="utf-8",
    )

    (templates_dir / "status.html").write_text(
        """
        <!doctype html>
        <html>
          <body>
            <h1>Status</h1>
            <div id="active-count">{{ active_count }}</div>
            <div id="completed-count">{{ completed_count }}</div>
            <div id="issue-count">{{ issue_count }}</div>
            {% include "_status_groups.html" %}
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    (templates_dir / "_status_groups.html").write_text(
        """
        {% for group_name, jobs in job_groups.items() %}
          <section class="status-group" data-group="{{ group_name }}">
            {% for job in jobs %}
              <article class="status-job">{{ job.job_id if job.job_id is defined else job['job_id'] }}</article>
            {% endfor %}
          </section>
        {% endfor %}
        """,
        encoding="utf-8",
    )

    request_handler = DummyRequestHandler()
    output_repository = DummyOutputRepository()
    job_service = DummyJobService()
    job_recovery_handler = DummyJobRecoveryHandler()

    app.config["APP_CONTAINER"] = SimpleNamespace(
        request_handler=request_handler,
        output_repository=output_repository,
        job_service=job_service,
        job_recovery_handler=job_recovery_handler,
    )

    app.register_blueprint(ui_blueprint)

    return app.test_client(), app.config["APP_CONTAINER"]


def test_index_renders(client):
    test_client, _ = client

    response = test_client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Index" in html
    assert 'id="outputs-count">2<' in html


@pytest.mark.parametrize(
    ("filter_name", "expected_call"),
    [
        ("active", (True, None)),
        ("completed", (False, "completed")),
        ("issues", (False, "issues")),
        ("all", (False, None)),
    ],
)
def test_status_page_filters(client, filter_name, expected_call):
    test_client, container = client

    response = test_client.get(f"/status?filter={filter_name}")

    assert response.status_code == 200
    assert container.job_service.all_status_calls[-1] == expected_call


def test_status_fragment_renders_groups(client):
    test_client, container = client

    response = test_client.get("/status/fragment?filter=issues")

    assert response.status_code == 200
    assert container.job_service.all_status_calls[-1] == (False, "issues")
    html = response.get_data(as_text=True)
    assert "job-123" in html


def test_job_fragment_renders_single_job_card(client):
    test_client, container = client

    response = test_client.get("/jobs/job-123/fragment")

    assert response.status_code == 200
    assert container.job_service.status_calls == ["job-123"]
    html = response.get_data(as_text=True)
    assert "Job Submitted" in html
    assert "job-123" in html
    assert "Laid to Rest" in html


def test_retry_job_redirects(client):
    test_client, container = client

    response = test_client.post("/jobs/job-123/retry", follow_redirects=False)

    assert response.status_code == 302
    assert container.job_recovery_handler.retry_calls == ["job-123"]
    assert "/status?filter=issues" in response.headers["Location"]


def test_delete_job_redirects(client):
    test_client, container = client

    response = test_client.post("/jobs/job-123/delete", follow_redirects=False)

    assert response.status_code == 302
    assert container.job_recovery_handler.delete_calls == ["job-123"]
    assert "/status?filter=issues" in response.headers["Location"]


def test_create_form_success_renders_success_card(client):
    test_client, container = client

    response = test_client.post(
        "/create",
        data={
            "youtube_url": "https://youtu.be/example",
            "output_name": "Laid to Rest",
            "poster_url": "https://image.tmdb.org/test.jpg",
            "poster_source_type": "url",
            "poster_zoom": "1.2",
            "poster_offset_x": "0.3",
            "poster_offset_y": "0.7",
            "poster_mode": "cover",
        },
    )

    assert response.status_code == 200
    assert len(container.request_handler.create_calls) == 1
    html = response.get_data(as_text=True)
    assert "Job Submitted" in html
    assert "job-create-123" in html
    assert "Laid to Rest" in html


@pytest.mark.parametrize(
    ("data", "expected_message"),
    [
        (
            {"youtube_url": ""},
            "youtube_url is required",
        ),
        (
            {
                "youtube_url": "https://youtu.be/example",
                "poster_url": "https://image.tmdb.org/test.jpg",
                "poster_source_type": "url",
                "poster_zoom": "abc",
            },
            "poster_zoom is invalid: must be a valid number",
        ),
    ],
)
def test_create_form_validation_errors_render_error_card(client, data, expected_message):
    test_client, _ = client

    response = test_client.post("/create", data=data)

    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "Request Failed" in html
    assert "Failed" in html
    assert expected_message in html
    assert "job-card-error" in html


def test_create_form_controller_render_error_renders_error_card(client):
    test_client, container = client
    container.request_handler.raise_on_create = ControllerRenderError("Custom create failure")

    response = test_client.post(
        "/create",
        data={"youtube_url": "https://youtu.be/example"},
    )

    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "Request Failed" in html
    assert "Custom create failure" in html


def test_create_form_unhandled_error_renders_server_error_card(client):
    test_client, container = client
    container.request_handler.raise_on_create = RuntimeError("boom")

    response = test_client.post(
        "/create",
        data={"youtube_url": "https://youtu.be/example"},
    )

    assert response.status_code == 500
    html = response.get_data(as_text=True)
    assert "Request Failed" in html
    assert "Something went wrong while submitting the create request." in html


def test_update_form_success_renders_success_card(client):
    test_client, container = client

    response = test_client.post(
        "/update",
        data={
            "output_name": "Laid to Rest",
            "poster_source_type": "local",
            "local_poster_file": "poster.jpg",
            "poster_zoom": "1.0",
            "poster_offset_x": "0.5",
            "poster_offset_y": "0.5",
            "poster_mode": "contain",
        },
    )

    assert response.status_code == 200
    assert len(container.request_handler.update_calls) == 1
    html = response.get_data(as_text=True)
    assert "Job Submitted" in html
    assert "job-update-123" in html
    assert "Laid to Rest" in html


@pytest.mark.parametrize(
    ("data", "expected_message"),
    [
        (
            {"output_name": ""},
            "output_name is required",
        ),
        (
            {
                "output_name": "Laid to Rest",
                "poster_source_type": "local",
                "local_poster_file": "poster.jpg",
                "poster_offset_x": "not-a-number",
            },
            "poster_offset_x is invalid: must be a valid number",
        ),
    ],
)
def test_update_form_validation_errors_render_error_card(client, data, expected_message):
    test_client, _ = client

    response = test_client.post("/update", data=data)

    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "Request Failed" in html
    assert expected_message in html
    assert "job-card-error" in html


def test_update_form_controller_render_error_renders_error_card(client):
    test_client, container = client
    container.request_handler.raise_on_update = ControllerRenderError("Custom update failure")

    response = test_client.post(
        "/update",
        data={"output_name": "Laid to Rest"},
    )

    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "Request Failed" in html
    assert "Custom update failure" in html


def test_update_form_unhandled_error_renders_server_error_card(client):
    test_client, container = client
    container.request_handler.raise_on_update = RuntimeError("boom")

    response = test_client.post(
        "/update",
        data={"output_name": "Laid to Rest"},
    )

    assert response.status_code == 500
    html = response.get_data(as_text=True)
    assert "Request Failed" in html
    assert "Something went wrong while submitting the update request." in html