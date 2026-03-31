"""RQ job functions."""

from rq import get_current_job

from app.config.container import build_container
from app.models.domain import PosterCropSettings
from app.models.requests import CreateMediaRequest, UpdateMediaRequest
from app.utils.logging_context import clear_job_id, set_job_id
from app.utils.logger_factory import get_logger


LOGGER = get_logger(__name__)


def process_create_request(request_payload: dict) -> dict:
    """Execute a queued create request."""
    job = get_current_job()
    set_job_id(job.id if job else "-")

    try:
        LOGGER.info("Starting create request job.")
        container = build_container()
        result = container.request_handler.process_create(CreateMediaRequest(**_inflate_payload(request_payload)))
        if job:
            job.meta["output_name"] = result.get("output_name")
            job.save_meta()
        LOGGER.info("Finished create request job successfully.")
        return result
    finally:
        clear_job_id()



def process_update_request(request_payload: dict) -> dict:
    """Execute a queued update request."""
    job = get_current_job()
    set_job_id(job.id if job else "-")

    try:
        LOGGER.info("Starting update request job.")
        container = build_container()
        result = container.request_handler.process_update(UpdateMediaRequest(**_inflate_payload(request_payload)))
        if job:
            job.meta["output_name"] = result.get("output_name")
            job.save_meta()
        LOGGER.info("Finished update request job successfully.")
        return result
    finally:
        clear_job_id()



def _inflate_payload(request_payload: dict) -> dict:
    """Convert nested dataclass dictionaries back into domain objects."""
    payload = dict(request_payload)
    crop_settings = payload.get("poster_crop_settings")
    if isinstance(crop_settings, dict):
        payload["poster_crop_settings"] = PosterCropSettings(**crop_settings)
    return payload
