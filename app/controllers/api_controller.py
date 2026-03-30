"""JSON API routes."""

from flask import Blueprint, current_app, jsonify, request, Response

from app.models.domain import PosterCropSettings
from app.models.requests import CreateMediaRequest, UpdateMediaRequest

api_blueprint = Blueprint("api", __name__, url_prefix="/api/v1")


@api_blueprint.post("/requests")
def create_request():
    """Submit a create request through the API."""
    payload = request.get_json(force=True, silent=False) or {}
    create_model = CreateMediaRequest(
        youtube_url=payload.get("youtube_url", "").strip(),
        output_name=_optional_value(payload.get("output_name")),
        poster_url=_optional_value(payload.get("poster_url")),
        background_url=_optional_value(payload.get("background_url")),
        chapters_text=_optional_value(payload.get("chapters_text")),
        poster_crop_settings=_poster_crop_settings(payload),
    )
    if not create_model.youtube_url:
        return jsonify({"error": "youtube_url is required"}), 400
    container = current_app.config["APP_CONTAINER"]
    response = container.request_handler.submit_create(create_model)
    return jsonify(response.to_dict()), 202


@api_blueprint.post("/updates")
def update_request():
    """Submit an update request through the API."""
    payload = request.get_json(force=True, silent=False) or {}
    update_model = UpdateMediaRequest(
        output_name=payload.get("output_name", "").strip(),
        poster_url=_poster_url_or_none(payload),
        local_poster_file=_local_poster_file_or_none(payload),
        background_url=_optional_value(payload.get("background_url")),
        chapters_text=_optional_value(payload.get("chapters_text")),
        poster_crop_settings=_poster_crop_settings(payload),
    )
    if not update_model.output_name:
        return jsonify({"error": "output_name is required"}), 400
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
    image_url = request.args.get("url", "").strip()
    if not image_url:
        return jsonify({"error": "url is required"}), 400
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
    image_url = request.args.get("url", "").strip()
    if not image_url:
        return jsonify({"error": "url is required"}), 400
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


def _resolve_local_poster_path():
    """Resolve a local poster file from request arguments."""
    output_name = request.args.get("output_name", "").strip()
    file_name = request.args.get("file", "").strip()
    if not output_name or not file_name:
        raise ValueError("output_name and file are required")
    container = current_app.config["APP_CONTAINER"]
    return container.output_repository.resolve_poster_file(output_name, file_name)


def _crop_settings_from_args() -> PosterCropSettings:
    """Build crop settings from query parameters."""
    return PosterCropSettings(
        zoom=float(request.args.get("zoom", "1.0")),
        offset_x=float(request.args.get("offset_x", "0.5")),
        offset_y=float(request.args.get("offset_y", "0.5")),
        mode=request.args.get("mode", "cover").strip() or "cover",
    )


def _poster_crop_settings(payload):
    """Build poster crop settings from request payload when provided."""
    if not (_poster_url_or_none(payload) or _local_poster_file_or_none(payload)):
        return None
    return PosterCropSettings(
        zoom=float(payload.get("poster_zoom", 1.0)),
        offset_x=float(payload.get("poster_offset_x", 0.5)),
        offset_y=float(payload.get("poster_offset_y", 0.5)),
        mode=(payload.get("poster_mode") or "cover").strip() or "cover",
    )


def _poster_url_or_none(payload):
    """Return a poster URL only when payload is using URL mode."""
    if (payload.get("poster_source_type") or "url").strip() != "url":
        return None
    return _optional_value(payload.get("poster_url"))


def _local_poster_file_or_none(payload):
    """Return a local poster file only when payload is using local mode."""
    if (payload.get("poster_source_type") or "url").strip() != "local":
        return None
    return _optional_value(payload.get("local_poster_file"))


def _optional_value(value):
    """Normalize empty strings to None."""
    return value.strip() if isinstance(value, str) and value.strip() else None
