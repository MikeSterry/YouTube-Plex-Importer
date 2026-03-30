"""Dependency container for the application."""

from dataclasses import dataclass

from redis import Redis
from rq import Queue

from app.clients.http_client import HttpClient
from app.clients.youtube_client import YoutubeClient
from app.config.settings import Settings
from app.handlers.media_request_handler import MediaRequestHandler
from app.repositories.job_repository import JobRepository
from app.repositories.output_repository import OutputRepository
from app.services.chapter_service import ChapterService
from app.services.filesystem_service import FilesystemService
from app.services.image_service import ImageService
from app.services.job_service import JobService
from app.services.media_service import MediaService
from app.services.metadata_service import MetadataService


@dataclass
class AppContainer:
    """Resolved dependency graph for the app."""

    settings: Settings
    request_handler: MediaRequestHandler
    job_service: JobService
    output_repository: OutputRepository
    image_service: ImageService



def build_container() -> AppContainer:
    """Create the full dependency container."""
    settings = Settings.load()
    redis_conn = Redis.from_url(settings.redis_url)
    queue = Queue(settings.queue_name, connection=redis_conn, default_timeout=settings.rq_default_timeout)

    filesystem_service = FilesystemService(settings)
    http_client = HttpClient(timeout=60)
    output_repository = OutputRepository(settings, filesystem_service)
    youtube_client = YoutubeClient(settings, filesystem_service)
    chapter_service = ChapterService()
    image_service = ImageService(settings, filesystem_service, http_client)
    metadata_service = MetadataService(settings, filesystem_service)
    media_service = MediaService(settings, filesystem_service, output_repository, youtube_client)
    job_repository = JobRepository(queue)
    job_service = JobService(job_repository)
    request_handler = MediaRequestHandler(
        output_repository=output_repository,
        media_service=media_service,
        image_service=image_service,
        chapter_service=chapter_service,
        metadata_service=metadata_service,
        job_service=job_service,
        filesystem_service=filesystem_service,
    )
    return AppContainer(
        settings=settings,
        request_handler=request_handler,
        job_service=job_service,
        output_repository=output_repository,
        image_service=image_service,
    )
