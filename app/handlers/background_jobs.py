"""RQ job functions."""

from rq import get_current_job

from app.config.container import build_container
from app.models.domain import PosterCropSettings
from app.models.requests import CreateMediaRequest, UpdateMediaRequest



def process_create_request(request_payload: dict) -> dict:
    """Execute a queued create request."""
    container = build_container()
    job = get_current_job()
    result = container.request_handler.process_create(CreateMediaRequest(**_inflate_payload(request_payload)))
    if job:
        job.meta["output_name"] = result.get("output_name")
        job.save_meta()
    return result



def process_update_request(request_payload: dict) -> dict:
    """Execute a queued update request."""
    container = build_container()
    job = get_current_job()
    result = container.request_handler.process_update(UpdateMediaRequest(**_inflate_payload(request_payload)))
    if job:
        job.meta["output_name"] = result.get("output_name")
        job.save_meta()
    return result



def _inflate_payload(request_payload: dict) -> dict:
    """Convert nested dataclass dictionaries back into domain objects."""
    payload = dict(request_payload)
    crop_settings = payload.get("poster_crop_settings")
    if isinstance(crop_settings, dict):
        payload["poster_crop_settings"] = PosterCropSettings(**crop_settings)
    return payload
