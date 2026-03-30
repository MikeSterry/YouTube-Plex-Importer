"""RQ worker entry point."""

from redis import Redis
from rq import Worker, Queue

from app.config.settings import Settings


def main() -> None:
    """Start the background worker."""
    settings = Settings.load()
    connection = Redis.from_url(settings.redis_url)
    worker = Worker([Queue(settings.queue_name, connection=connection)], connection=connection)
    worker.work()


if __name__ == "__main__":
    main()
