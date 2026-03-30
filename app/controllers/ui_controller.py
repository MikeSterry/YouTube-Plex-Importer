"""UI routes."""

from flask import Blueprint, current_app, redirect, render_template, request, url_for

from app.models.domain import PosterCropSettings
from app.models.requests import CreateMediaRequest, UpdateMediaRequest

ui_blueprint = Blueprint("ui", __name__)


@ui_blueprint.get("/")
def index():
    """Render the main UI with create and update tabs."""
    container = current_app.config["APP_CONTAINER"]
    outputs = container.output_repository.list_outputs()
    return render_template("index.html", outputs=outputs, result=None)


@ui_blueprint.post("/create")
def create_form():
    """Submit a create request from the HTML form."""
    model = CreateMediaRequest(
        youtube_url=request.form.get("youtube_url", "").strip(),
        output_name=_optional_value(request.form.get("output_name")),
        poster_url=_optional_value(request.form.get("poster_url")),
        background_url=_optional_value(request.form.get("background_url")),
        chapters_text=_optional_value(request.form.get("chapters_text")),
        poster_crop_settings=_poster_crop_settings(request.form),
    )
    if not model.youtube_url:
        return redirect(url_for("ui.index"))
    container = current_app.config["APP_CONTAINER"]
    result = container.request_handler.submit_create(model)
    outputs = container.output_repository.list_outputs()
    return render_template("index.html", outputs=outputs, result=result.to_dict())


@ui_blueprint.post("/update")
def update_form():
    """Submit an update request from the HTML form."""
    model = UpdateMediaRequest(
        output_name=request.form.get("output_name", "").strip(),
        poster_url=_poster_url_or_none(request.form),
        local_poster_file=_local_poster_file_or_none(request.form),
        background_url=_optional_value(request.form.get("background_url")),
        chapters_text=_optional_value(request.form.get("chapters_text")),
        poster_crop_settings=_poster_crop_settings(request.form),
    )
    if not model.output_name:
        return redirect(url_for("ui.index"))
    container = current_app.config["APP_CONTAINER"]
    result = container.request_handler.submit_update(model)
    outputs = container.output_repository.list_outputs()
    return render_template("index.html", outputs=outputs, result=result.to_dict())


def _poster_crop_settings(form_data):
    """Build poster crop settings from submitted form data."""
    if not (_poster_url_or_none(form_data) or _local_poster_file_or_none(form_data)):
        return None
    return PosterCropSettings(
        zoom=float(form_data.get("poster_zoom", "1.0") or 1.0),
        offset_x=float(form_data.get("poster_offset_x", "0.5") or 0.5),
        offset_y=float(form_data.get("poster_offset_y", "0.5") or 0.5),
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


def _optional_value(value):
    """Normalize empty form values to None."""
    return value.strip() if isinstance(value, str) and value.strip() else None
