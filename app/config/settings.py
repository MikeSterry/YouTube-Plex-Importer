"""Application settings."""

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Strongly typed application settings."""

    secret_key: str
    redis_url: str
    queue_name: str
    rq_default_timeout: int
    inprogress_dir: str
    output_dir: str
    app_user_id: int
    app_group_id: int
    app_file_mode: int
    app_dir_mode: int
    ytdlp_format: str
    ffmpeg_bin: str
    ffprobe_bin: str
    mkvmerge_bin: str
    max_content_length: int

    @staticmethod
    def load() -> "Settings":
        """Load settings from environment variables."""
        load_dotenv("properties")
        return Settings(
            secret_key=os.getenv("SECRET_KEY", "change-me"),
            redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
            queue_name=os.getenv("RQ_QUEUE_NAME", "youtube_mkv_jobs"),
            rq_default_timeout=int(os.getenv("RQ_DEFAULT_TIMEOUT", "7200")),
            inprogress_dir=os.getenv("INPROGRESS_DIR", "/inprogress"),
            output_dir=os.getenv("OUTPUT_DIR", "/output"),
            app_user_id=int(os.getenv("APP_USER_ID", "1000")),
            app_group_id=int(os.getenv("APP_GROUP_ID", "1000")),
            app_file_mode=int(os.getenv("APP_FILE_MODE", "0o775"), 8),
            app_dir_mode=int(os.getenv("APP_DIR_MODE", "0o775"), 8),
            ytdlp_format=os.getenv("YTDLP_FORMAT", "bv*+ba/b"),
            ffmpeg_bin=os.getenv("FFMPEG_BIN", "ffmpeg"),
            mkvmerge_bin=os.getenv("MKVMERGE_BIN", "mkvmerge"),
            ffprobe_bin=os.getenv("FFPROBE_BIN", "ffprobe"),
            max_content_length=int(os.getenv("MAX_CONTENT_LENGTH", str(16 * 1024 * 1024))),
        )
