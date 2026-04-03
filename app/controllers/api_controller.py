"""JSON API routes."""

from __future__ import annotations

from flask import Blueprint, Response, current_app, jsonify, request

from app.exceptions import (
    InvalidFieldError,
    InvalidJsonError,
    MissingFieldError,
)
from app.models.domain import PosterCropSettings
from app.models.requests import CreateMediaRequest, UpdateMediaRequest

api_blueprint = Blueprint("api", __name__, url_prefix="/api/v1")


@api_blueprint.post("/requests")
def create_request():
    """Submit a create request through the API."""
    payload = _json_payload()

    create_model = CreateMediaRequest(
        youtube_url=_required_string(payload, "youtube_url"),
        output_name=_optional_value(payload.get("output_name")),
        poster_url=_optional_value(payload.get("poster_url")),
        background_url=_optional_value(payload.get("background_url")),
        chapters_text=_optional_value(payload.get("chapters_text")),
        poster_crop_settings=_poster_crop_settings(payload),
    )

    container = current_app.config["APP_CONTAINER"]
    response = container.request_handler.submit_create(create_model)
    return jsonify(response.to_dict()), 202


@api_blueprint.post("/updates")
def update_request():
    """Submit an update request through the API."""
    payload = _json_payload()

    update_model = UpdateMediaRequest(
        output_name=_required_string(payload, "output_name"),
        poster_url=_poster_url_or_none(payload),
        local_poster_file=_local_poster_file_or_none(payload),
        background_url=_optional_value(payload.get("background_url")),
        chapters_text=_optional_value(payload.get("chapters_text")),
        poster_crop_settings=_poster_crop_settings(payload),
    )

    container = current_app.config["APP_CONTAINER"]
    response = container.request_handler.submit_update(update_model)
    return jsonify(response.to_dict()), 202


@api_blueprint.get("/outputs")
def list_outputs():
    """Return output folders for the update dropdown and API consumers."""
    container = current_app.config["APP_CONTAINER"]
    outputs = [entry.to_dict() for entry in container.output_repository.list_outputs()]
    return jsonify({"outputs": outputs})


@api_blueprint.get("/outputs/<path:output_name>/poster-files")
def list_poster_files(output_name: str):
    """Return editable local poster files for the selected output."""
    container = current_app.config["APP_CONTAINER"]
    files = container.output_repository.list_poster_files(output_name)
    return jsonify({"output_name": output_name, "poster_files": files})


@api_blueprint.get("/jobs/<job_id>")
def job_status(job_id: str):
    """Return background job status information."""
    container = current_app.config["APP_CONTAINER"]
    response = container.job_service.get_status(job_id)
    return jsonify(response.to_dict())


@api_blueprint.get("/artwork/source")
def artwork_source():
    """Proxy a remote artwork image so the browser can edit it without cross-origin issues."""
    image_url = _required_query_string("url")
    container = current_app.config["APP_CONTAINER"]
    image_bytes, content_type = container.image_service.fetch_source_bytes(image_url)
    return Response(image_bytes, mimetype=content_type)


@api_blueprint.get("/artwork/local-source")
def local_artwork_source():
    """Return a local poster image from an existing output folder."""
    poster_path = _resolve_local_poster_path()
    container = current_app.config["APP_CONTAINER"]
    image_bytes, content_type = container.image_service.fetch_local_source_bytes(poster_path)
    return Response(image_bytes, mimetype=content_type)


@api_blueprint.get("/artwork/poster-preview")
def poster_preview():
    """Render a poster preview from remote source artwork and crop settings."""
    image_url = _required_query_string("url")
    crop_settings = _crop_settings_from_args()
    container = current_app.config["APP_CONTAINER"]
    image_bytes = container.image_service.build_poster_preview_bytes(image_url, crop_settings)
    return Response(image_bytes, mimetype="image/jpeg")


@api_blueprint.get("/artwork/local-poster-preview")
def local_poster_preview():
    """Render a poster preview from a local poster file and crop settings."""
    poster_path = _resolve_local_poster_path()
    crop_settings = _crop_settings_from_args()
    container = current_app.config["APP_CONTAINER"]
    image_bytes = container.image_service.build_local_poster_preview_bytes(poster_path, crop_settings)
    return Response(image_bytes, mimetype="image/jpeg")


def _json_payload() -> dict:
    """Read and validate the JSON request body."""
    payload = request.get_json(force=True, silent=True)
    if payload is None:
        raise InvalidJsonError()
    if not isinstance(payload, dict):
        raise InvalidJsonError("Request body must be a JSON object.")
    return payload


def _resolve_local_poster_path():
    """Resolve a local poster file from request arguments."""
    output_name = _required_query_string("output_name")
    file_name = _required_query_string("file")
    container = current_app.config["APP_CONTAINER"]
    return container.output_repository.resolve_poster_file(output_name, file_name)


def _crop_settings_from_args() -> PosterCropSettings:
    """Build crop settings from query parameters."""
    return PosterCropSettings(
        zoom=_float_arg("zoom", 1.0),
        offset_x=_float_arg("offset_x", 0.5),
        offset_y=_float_arg("offset_y", 0.5),
        mode=(request.args.get("mode", "cover").strip() or "cover"),
    )


def _poster_crop_settings(payload: dict):
    """Build poster crop settings from request payload when provided."""
    if not (_poster_url_or_none(payload) or _local_poster_file_or_none(payload)):
        return None

    return PosterCropSettings(
        zoom=_float_value(payload.get("poster_zoom", 1.0), "poster_zoom"),
        offset_x=_float_value(payload.get("poster_offset_x", 0.5), "poster_offset_x"),
        offset_y=_float_value(payload.get("poster_offset_y", 0.5), "poster_offset_y"),
        mode=((payload.get("poster_mode") or "cover").strip() or "cover"),
    )


def _poster_url_or_none(payload: dict):
    """Return a poster URL only when payload is using URL mode."""
    if (payload.get("poster_source_type") or "url").strip() != "url":
        return None
    return _optional_value(payload.get("poster_url"))


def _local_poster_file_or_none(payload: dict):
    """Return a local poster file only when payload is using local mode."""
    if (payload.get("poster_source_type") or "url").strip() != "local":
        return None
    return _optional_value(payload.get("local_poster_file"))


def _required_string(payload: dict, field_name: str) -> str:
    """Return a required non-empty string field."""
    value = payload.get(field_name, "")
    if not isinstance(value, str) or not value.strip():
        raise MissingFieldError(field_name)
    return value.strip()


def _required_query_string(field_name: str) -> str:
    """Return a required query parameter."""
    value = request.args.get(field_name, "")
    if not isinstance(value, str) or not value.strip():
        raise MissingFieldError(field_name)
    return value.strip()


def _float_arg(field_name: str, default: float) -> float:
    """Read a float from query parameters."""
    raw_value = request.args.get(field_name)
    if raw_value is None or str(raw_value).strip() == "":
        return default
    return _float_value(raw_value, field_name)


def _float_value(raw_value, field_name: str) -> float:
    """Convert a value to float with a custom validation error."""
    try:
        return float(raw_value)
    except (TypeError, ValueError) as exc:
        raise InvalidFieldError(field_name, "must be a valid number") from exc


def _optional_value(value):
    """Normalize empty strings to None."""
    return value.strip() if isinstance(value, str) and value.strip() else None