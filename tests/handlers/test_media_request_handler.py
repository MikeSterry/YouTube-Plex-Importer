from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import app.handlers.media_request_handler as media_request_handler_module
from app.handlers.media_request_handler import MediaRequestHandler
from app.models.domain import PosterCropSettings
from app.models.requests import CreateMediaRequest, UpdateMediaRequest


class DummyOutputRepository:
    def __init__(self):
        self.find_update_target_calls = []
        self.resolve_poster_file_calls = []
        self.update_target = SimpleNamespace(
            output_name="Existing Output",
            directory=Path("/library/existing-output"),
            mkv_path=Path("/library/existing-output/movie.mkv"),
        )
        self.poster_path = Path("/library/existing-output/poster.png")

    def find_update_target(self, output_name):
        self.find_update_target_calls.append(output_name)
        return self.update_target

    def resolve_poster_file(self, output_name, local_poster_file):
        self.resolve_poster_file_calls.append((output_name, local_poster_file))
        return self.poster_path


class DummyMediaService:
    def __init__(self):
        self.download_calls = []
        self.finalize_calls = []
        self.download_result = SimpleNamespace(
            output_name="Created Output",
            video_path=Path("/tmp/work/video.mkv"),
        )
        self.work_dir = Path("/tmp/work")
        self.final_dir = Path("/library/created-output")
        self.final_video = self.final_dir / "Created Output.mkv"

    def download_youtube_video(self, youtube_url, output_name, job_id):
        self.download_calls.append((youtube_url, output_name, job_id))
        return self.download_result, self.work_dir, self.final_dir

    def finalize_video(self, video_path, final_dir):
        self.finalize_calls.append((video_path, final_dir))
        return self.final_video


class DummyImageService:
    def __init__(self):
        self.process_poster_calls = []
        self.process_background_calls = []
        self.process_local_poster_calls = []

    def process_poster(self, poster_url, output_dir, crop_settings):
        self.process_poster_calls.append((poster_url, output_dir, crop_settings))

    def process_background(self, background_url, output_dir):
        self.process_background_calls.append((background_url, output_dir))

    def process_local_poster(self, poster_path, crop_settings):
        self.process_local_poster_calls.append((poster_path, crop_settings))


class DummyChapterService:
    def __init__(self):
        self.parse_calls = []
        self.to_metadata_text_calls = []

    def parse(self, chapters_text):
        self.parse_calls.append(chapters_text)
        return [{"start": "00:00:00", "title": "Intro"}]

    def to_metadata_text(self, chapters):
        self.to_metadata_text_calls.append(chapters)
        return ";FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=1000\ntitle=Intro\n"


class DummyMetadataService:
    def __init__(self):
        self.merge_chapters_calls = []
        self.merged_video = Path("/library/created-output/Created Output.chapters.mkv")

    def merge_chapters(self, source_video, chapter_file, temp_output):
        self.merge_chapters_calls.append((source_video, chapter_file, temp_output))
        return self.merged_video


class DummyJobService:
    def __init__(self):
        self.enqueue_create_calls = []
        self.enqueue_update_calls = []

    def enqueue_create(self, payload):
        self.enqueue_create_calls.append(payload)
        return {"job_id": "create-job-123", "status": "Queued"}

    def enqueue_update(self, payload):
        self.enqueue_update_calls.append(payload)
        return {"job_id": "update-job-123", "status": "Queued"}


class DummyFilesystemService:
    def __init__(self):
        self.write_text_calls = []
        self.normalize_file_calls = []

    def write_text(self, path, text):
        self.write_text_calls.append((path, text))
        return path

    def normalize_file(self, path):
        self.normalize_file_calls.append(path)


@pytest.fixture()
def handler():
    output_repository = DummyOutputRepository()
    media_service = DummyMediaService()
    image_service = DummyImageService()
    chapter_service = DummyChapterService()
    metadata_service = DummyMetadataService()
    job_service = DummyJobService()
    filesystem_service = DummyFilesystemService()

    instance = MediaRequestHandler(
        output_repository=output_repository,
        media_service=media_service,
        image_service=image_service,
        chapter_service=chapter_service,
        metadata_service=metadata_service,
        job_service=job_service,
        filesystem_service=filesystem_service,
    )

    return SimpleNamespace(
        handler=instance,
        output_repository=output_repository,
        media_service=media_service,
        image_service=image_service,
        chapter_service=chapter_service,
        metadata_service=metadata_service,
        job_service=job_service,
        filesystem_service=filesystem_service,
    )


def test_submit_create_enqueues_serialized_request(handler):
    request = CreateMediaRequest(
        youtube_url="https://youtu.be/example",
        output_name="Created Output",
        poster_url="https://image.test/poster.jpg",
        background_url="https://image.test/background.jpg",
        chapters_text="00:00 Intro",
        poster_crop_settings=PosterCropSettings(
            zoom=1.2,
            offset_x=0.3,
            offset_y=0.7,
            mode="cover",
        ),
    )

    result = handler.handler.submit_create(request)

    assert result == {"job_id": "create-job-123", "status": "Queued"}
    assert len(handler.job_service.enqueue_create_calls) == 1
    payload = handler.job_service.enqueue_create_calls[0]
    assert payload["youtube_url"] == "https://youtu.be/example"
    assert payload["output_name"] == "Created Output"
    assert payload["poster_url"] == "https://image.test/poster.jpg"
    assert payload["background_url"] == "https://image.test/background.jpg"
    assert payload["chapters_text"] == "00:00 Intro"
    assert payload["poster_crop_settings"]["zoom"] == 1.2


def test_submit_update_enqueues_serialized_request(handler):
    request = UpdateMediaRequest(
        output_name="Existing Output",
        poster_url="https://image.test/poster.jpg",
        local_poster_file=None,
        background_url="https://image.test/background.jpg",
        chapters_text="00:00 Intro",
        poster_crop_settings=PosterCropSettings(
            zoom=1.1,
            offset_x=0.5,
            offset_y=0.6,
            mode="contain",
        ),
    )

    result = handler.handler.submit_update(request)

    assert result == {"job_id": "update-job-123", "status": "Queued"}
    assert len(handler.job_service.enqueue_update_calls) == 1
    payload = handler.job_service.enqueue_update_calls[0]
    assert payload["output_name"] == "Existing Output"
    assert payload["poster_url"] == "https://image.test/poster.jpg"
    assert payload["background_url"] == "https://image.test/background.jpg"
    assert payload["chapters_text"] == "00:00 Intro"
    assert payload["poster_crop_settings"]["mode"] == "contain"


def test_process_create_happy_path_with_all_optional_steps(handler, monkeypatch):
    cleanup_calls = []
    apply_chapters_calls = []

    monkeypatch.setattr(
        media_request_handler_module,
        "get_current_job",
        lambda: SimpleNamespace(id="job-123"),
    )
    monkeypatch.setattr(
        handler.handler,
        "_cleanup",
        lambda work_dir: cleanup_calls.append(work_dir),
    )
    monkeypatch.setattr(
        handler.handler,
        "_apply_chapters",
        lambda chapters_text, output_dir, source_video: apply_chapters_calls.append(
            (chapters_text, output_dir, source_video)
        ) or Path("/library/created-output/Created Output.with-chapters.mkv"),
    )

    request = CreateMediaRequest(
        youtube_url="https://youtu.be/example",
        output_name="Created Output",
        poster_url="https://image.test/poster.jpg",
        background_url="https://image.test/background.jpg",
        chapters_text="00:00 Intro",
        poster_crop_settings=PosterCropSettings(
            zoom=1.2,
            offset_x=0.3,
            offset_y=0.7,
            mode="cover",
        ),
    )

    result = handler.handler.process_create(request)

    assert result == {
        "output_name": "Created Output",
        "video_path": "/library/created-output/Created Output.with-chapters.mkv",
    }

    assert handler.media_service.download_calls == [
        ("https://youtu.be/example", "Created Output", "job-123")
    ]
    assert handler.media_service.finalize_calls == [
        (Path("/tmp/work/video.mkv"), Path("/library/created-output"))
    ]
    assert apply_chapters_calls == [
        (
            "00:00 Intro",
            Path("/library/created-output"),
            Path("/library/created-output/Created Output.mkv"),
        )
    ]
    assert handler.image_service.process_poster_calls == [
        (
            "https://image.test/poster.jpg",
            Path("/library/created-output"),
            request.poster_crop_settings,
        )
    ]
    assert handler.image_service.process_background_calls == [
        ("https://image.test/background.jpg", Path("/library/created-output"))
    ]
    assert cleanup_calls == [Path("/tmp/work")]


def test_process_create_without_optional_steps(handler, monkeypatch):
    cleanup_calls = []

    monkeypatch.setattr(media_request_handler_module, "get_current_job", lambda: None)
    monkeypatch.setattr(
        handler.handler,
        "_cleanup",
        lambda work_dir: cleanup_calls.append(work_dir),
    )

    request = CreateMediaRequest(
        youtube_url="https://youtu.be/example",
        output_name=None,
        poster_url=None,
        background_url=None,
        chapters_text=None,
        poster_crop_settings=None,
    )

    result = handler.handler.process_create(request)

    assert result == {
        "output_name": "Created Output",
        "video_path": "/library/created-output/Created Output.mkv",
    }
    assert handler.media_service.download_calls == [
        ("https://youtu.be/example", None, None)
    ]
    assert handler.image_service.process_poster_calls == []
    assert handler.image_service.process_background_calls == []
    assert cleanup_calls == [Path("/tmp/work")]


def test_process_update_with_remote_poster_background_and_chapters(handler, monkeypatch):
    apply_chapters_calls = []

    monkeypatch.setattr(
        handler.handler,
        "_apply_chapters",
        lambda chapters_text, output_dir, source_video: apply_chapters_calls.append(
            (chapters_text, output_dir, source_video)
        ) or source_video,
    )

    request = UpdateMediaRequest(
        output_name="Existing Output",
        poster_url="https://image.test/poster.jpg",
        local_poster_file=None,
        background_url="https://image.test/background.jpg",
        chapters_text="00:00 Intro",
        poster_crop_settings=PosterCropSettings(
            zoom=1.4,
            offset_x=0.2,
            offset_y=0.8,
            mode="cover",
        ),
    )

    result = handler.handler.process_update(request)

    assert result == {
        "output_name": "Existing Output",
        "video_path": "/library/existing-output/movie.mkv",
    }
    assert handler.output_repository.find_update_target_calls == ["Existing Output"]
    assert apply_chapters_calls == [
        (
            "00:00 Intro",
            Path("/library/existing-output"),
            Path("/library/existing-output/movie.mkv"),
        )
    ]
    assert handler.image_service.process_poster_calls == [
        (
            "https://image.test/poster.jpg",
            Path("/library/existing-output"),
            request.poster_crop_settings,
        )
    ]
    assert handler.image_service.process_background_calls == [
        ("https://image.test/background.jpg", Path("/library/existing-output"))
    ]
    assert handler.image_service.process_local_poster_calls == []


def test_process_update_with_local_poster(handler):
    request = UpdateMediaRequest(
        output_name="Existing Output",
        poster_url=None,
        local_poster_file="poster.png",
        background_url=None,
        chapters_text=None,
        poster_crop_settings=PosterCropSettings(
            zoom=1.0,
            offset_x=0.5,
            offset_y=0.5,
            mode="contain",
        ),
    )

    result = handler.handler.process_update(request)

    assert result == {
        "output_name": "Existing Output",
        "video_path": "/library/existing-output/movie.mkv",
    }
    assert handler.output_repository.find_update_target_calls == ["Existing Output"]
    assert handler.output_repository.resolve_poster_file_calls == [
        ("Existing Output", "poster.png")
    ]
    assert handler.image_service.process_local_poster_calls == [
        (
            Path("/library/existing-output/poster.png"),
            request.poster_crop_settings,
        )
    ]
    assert handler.image_service.process_poster_calls == []
    assert handler.image_service.process_background_calls == []


def test_process_update_skips_chapters_when_no_video(handler, monkeypatch):
    apply_chapters_calls = []
    handler.output_repository.update_target = SimpleNamespace(
        output_name="Existing Output",
        directory=Path("/library/existing-output"),
        mkv_path=None,
    )

    monkeypatch.setattr(
        handler.handler,
        "_apply_chapters",
        lambda chapters_text, output_dir, source_video: apply_chapters_calls.append(
            (chapters_text, output_dir, source_video)
        ),
    )

    request = UpdateMediaRequest(
        output_name="Existing Output",
        poster_url=None,
        local_poster_file=None,
        background_url=None,
        chapters_text="00:00 Intro",
        poster_crop_settings=None,
    )

    result = handler.handler.process_update(request)

    assert result == {
        "output_name": "Existing Output",
        "video_path": None,
    }
    assert apply_chapters_calls == []


def test_apply_chapters_writes_metadata_merges_and_normalizes(handler, monkeypatch):
    move_calls = []

    monkeypatch.setattr(
        media_request_handler_module.shutil,
        "move",
        lambda src, dst: move_calls.append((src, dst)),
    )

    output_dir = Path("/library/created-output")
    source_video = output_dir / "Created Output.mkv"

    result = handler.handler._apply_chapters(
        chapters_text="00:00 Intro",
        output_dir=output_dir,
        source_video=source_video,
    )

    expected_chapter_file = output_dir / "chapter.txt"
    expected_temp_output = output_dir / "Created Output.chapters.mkv"

    assert result == source_video
    assert handler.chapter_service.parse_calls == ["00:00 Intro"]
    assert handler.chapter_service.to_metadata_text_calls == [
        [{"start": "00:00:00", "title": "Intro"}]
    ]
    assert handler.filesystem_service.write_text_calls == [
        (
            expected_chapter_file,
            ";FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=1000\ntitle=Intro\n",
        )
    ]
    assert handler.metadata_service.merge_chapters_calls == [
        (source_video, expected_chapter_file, expected_temp_output)
    ]
    assert move_calls == [
        (
            "/library/created-output/Created Output.chapters.mkv",
            "/library/created-output/Created Output.mkv",
        )
    ]
    assert handler.filesystem_service.normalize_file_calls == [source_video]


def test_cleanup_removes_work_dir(handler, monkeypatch):
    rmtree_calls = []

    monkeypatch.setattr(
        media_request_handler_module.shutil,
        "rmtree",
        lambda work_dir, ignore_errors: rmtree_calls.append((work_dir, ignore_errors)),
    )

    handler.handler._cleanup(Path("/tmp/work"))

    assert rmtree_calls == [(Path("/tmp/work"), True)]