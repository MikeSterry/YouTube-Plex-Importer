"""UI routes."""

from __future__ import annotations

import logging

from flask import Blueprint, current_app, redirect, render_template, request, url_for

from app.exceptions import ControllerRenderError, InvalidFieldError, MissingFieldError
from app.models.domain import PosterCropSettings
from app.models.requests import CreateMediaRequest, UpdateMediaRequest

LOGGER = logging.getLogger(__name__)

ui_blueprint = Blueprint("ui", __name__)

INDEX_HTML = "index.html"
STATUS_HTML = "status.html"
STATUS_GROUPS_PARTIAL = "_status_groups.html"
JOB_CARD_PARTIAL = "_job_result_card.html"


@ui_blueprint.get("/")
def index():
    """Render the main UI with create and update tabs."""
    container = current_app.config["APP_CONTAINER"]
    outputs = container.output_repository.list_outputs()
    return render_template(INDEX_HTML, result=None, outputs=outputs)


@ui_blueprint.get("/status")
def status_page():
    """Render the status page."""
    container = current_app.config["APP_CONTAINER"]
    filter_name = (request.args.get("filter") or "active").strip().lower()
    active_only, group = _status_filter_options(filter_name)
    collection = container.job_service.get_all_statuses(
        active_only=active_only,
        group=group,
    )
    return render_template(
        STATUS_HTML,
        job_groups=collection.grouped(),
        filter_name=filter_name,
        active_count=collection.active_count,
        completed_count=collection.completed_count,
        issue_count=collection.issue_count,
    )


@ui_blueprint.get("/status/fragment")
def status_fragment():
    """Render only the status group portion for polling."""
    container = current_app.config["APP_CONTAINER"]
    filter_name = (request.args.get("filter") or "active").strip().lower()
    active_only, group = _status_filter_options(filter_name)
    collection = container.job_service.get_all_statuses(
        active_only=active_only,
        group=group,
    )
    return render_template(
        STATUS_GROUPS_PARTIAL,
        job_groups=collection.grouped(),
    )


@ui_blueprint.get("/jobs/<job_id>/fragment")
def job_fragment(job_id: str):
    """Render a single job card for polling refresh."""
    container = current_app.config["APP_CONTAINER"]
    result = container.job_service.get_status(job_id)
    return render_template(JOB_CARD_PARTIAL, result=result.to_dict())


@ui_blueprint.post("/jobs/<job_id>/retry")
def retry_job(job_id: str):
    """Retry a failed/stopped/canceled job."""
    container = current_app.config["APP_CONTAINER"]
    container.job_recovery_handler.retry_job(job_id)
    return redirect(url_for("ui.status_page", filter="issues"))


@ui_blueprint.post("/jobs/<job_id>/delete")
def delete_job(job_id: str):
    """Delete a failed/stopped/canceled job and clean up artifacts."""
    container = current_app.config["APP_CONTAINER"]
    container.job_recovery_handler.delete_job(job_id)
    return redirect(url_for("ui.status_page", filter="issues"))


@ui_blueprint.post("/create")
def create_form():
    """Submit a create request from the HTML form."""
    container = current_app.config["APP_CONTAINER"]
    outputs = container.output_repository.list_outputs()

    try:
        model = CreateMediaRequest(
            youtube_url=_required_form_value("youtube_url"),
            output_name=_optional_value(request.form.get("output_name")),
            poster_url=_optional_value(request.form.get("poster_url")),
            background_url=_optional_value(request.form.get("background_url")),
            chapters_text=_optional_value(request.form.get("chapters_text")),
            poster_crop_settings=_poster_crop_settings(request.form),
        )
        result = container.request_handler.submit_create(model)
        return render_template(INDEX_HTML, result=result.to_dict(), outputs=outputs)
    except (MissingFieldError, InvalidFieldError, ControllerRenderError) as exc:
        LOGGER.info("Create form validation failed: %s", exc)
        return render_template(INDEX_HTML, result=_error_result(str(exc)), outputs=outputs), 400
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("Create form failed unexpectedly", exc_info=exc)
        return (
            render_template(
                INDEX_HTML,
                result=_error_result("Something went wrong while submitting the create request."),
                outputs=outputs,
            ),
            500,
        )


@ui_blueprint.post("/update")
def update_form():
    """Submit an update request from the HTML form."""
    container = current_app.config["APP_CONTAINER"]
    outputs = container.output_repository.list_outputs()

    try:
        model = UpdateMediaRequest(
            output_name=_required_form_value("output_name"),
            poster_url=_poster_url_or_none(request.form),
            local_poster_file=_local_poster_file_or_none(request.form),
            background_url=_optional_value(request.form.get("background_url")),
            chapters_text=_optional_value(request.form.get("chapters_text")),
            poster_crop_settings=_poster_crop_settings(request.form),
        )
        result = container.request_handler.submit_update(model)
        return render_template(INDEX_HTML, result=result.to_dict(), outputs=outputs)
    except (MissingFieldError, InvalidFieldError, ControllerRenderError) as exc:
        LOGGER.info("Update form validation failed: %s", exc)
        return render_template(INDEX_HTML, result=_error_result(str(exc)), outputs=outputs), 400
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("Update form failed unexpectedly", exc_info=exc)
        return (
            render_template(
                INDEX_HTML,
                result=_error_result("Something went wrong while submitting the update request."),
                outputs=outputs,
            ),
            500,
        )


def _status_filter_options(filter_name: str) -> tuple[bool, str | None]:
    """Return service filter options for the UI status filter."""
    active_only = filter_name == "active"
    group = None

    if filter_name == "completed":
        group = "completed"
    elif filter_name == "issues":
        group = "issues"
    elif filter_name == "all":
        active_only = False

    return active_only, group


def _poster_crop_settings(form_data):
    """Build poster crop settings from submitted form data."""
    if not (_poster_url_or_none(form_data) or _local_poster_file_or_none(form_data)):
        return None

    return PosterCropSettings(
        zoom=_float_form_value(form_data.get("poster_zoom", "1.0"), "poster_zoom", 1.0),
        offset_x=_float_form_value(form_data.get("poster_offset_x", "0.5"), "poster_offset_x", 0.5),
        offset_y=_float_form_value(form_data.get("poster_offset_y", "0.5"), "poster_offset_y", 0.5),
        mode=(form_data.get("poster_mode") or "cover").strip() or "cover",
    )


def _poster_url_or_none(form_data):
    """Return a poster URL only when the form is using URL mode."""
    if (form_data.get("poster_source_type") or "url").strip() != "url":
        return None
    return _optional_value(form_data.get("poster_url"))


def _local_poster_file_or_none(form_data):
    """Return a local poster file only when the form is using local mode."""
    if (form_data.get("poster_source_type") or "url").strip() != "local":
        return None
    return _optional_value(form_data.get("local_poster_file"))


def _required_form_value(field_name: str) -> str:
    """Return a required non-empty form field."""
    value = request.form.get(field_name, "")
    if not isinstance(value, str) or not value.strip():
        raise MissingFieldError(field_name)
    return value.strip()


def _float_form_value(raw_value, field_name: str, default: float) -> float:
    """Convert a form field into a float with a friendly validation error."""
    if raw_value is None or str(raw_value).strip() == "":
        return default

    try:
        return float(raw_value)
    except (TypeError, ValueError) as exc:
        raise InvalidFieldError(field_name, "must be a valid number") from exc


def _optional_value(value):
    """Normalize empty form values to None."""
    return value.strip() if isinstance(value, str) and value.strip() else None


def _error_result(message: str) -> dict:
    """Create a template-friendly error card payload."""
    return {
        "job_id": "Request error",
        "status": "Failed",
        "status_css_class": "status-failed",
        "output_name": "-",
        "created_at": "-",
        "started_at": "-",
        "finished_at": "-",
        "duration_display": "-",
        "error_message": message,
        "is_error": True,
    }