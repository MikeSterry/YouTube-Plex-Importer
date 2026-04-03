

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.domain import DownloadResult
from app.services.media_service import MediaService


class DummyFilesystemService:
    def __init__(self):
        self.move_to_directory_calls = []
        self.return_value = Path("/library/output/final.mkv")

    def move_to_directory(self, video_path: Path, final_dir: Path) -> Path:
        self.move_to_directory_calls.append((video_path, final_dir))
        return self.return_value


class DummyOutputRepository:
    def __init__(self):
        self.create_work_dir_calls = []
        self.create_output_dir_calls = []
        self.work_dir = Path("/tmp/inprogress/job-abc")
        self.output_dir = Path("/library/output/Movie One")

    def create_work_dir(self, name: str) -> Path:
        self.create_work_dir_calls.append(name)
        return self.work_dir

    def create_output_dir(self, output_name: str) -> Path:
        self.create_output_dir_calls.append(output_name)
        return self.output_dir


class DummyYoutubeClient:
    def __init__(self):
        self.download_best_mkv_calls = []
        self.return_value = DownloadResult(
            title="Source Title",
            output_name="Movie One",
            video_path=Path("/tmp/inprogress/job-abc/Movie One.mkv"),
            aux_files=[Path("/tmp/inprogress/job-abc/poster.jpg")],
        )

    def download_best_mkv(self, youtube_url: str, work_dir: Path, desired_output_name: str | None):
        self.download_best_mkv_calls.append((youtube_url, work_dir, desired_output_name))
        return self.return_value


@pytest.fixture()
def settings():
    return SimpleNamespace()


@pytest.fixture()
def filesystem_service():
    return DummyFilesystemService()


@pytest.fixture()
def output_repository():
    return DummyOutputRepository()


@pytest.fixture()
def youtube_client():
    return DummyYoutubeClient()


@pytest.fixture()
def service(settings, filesystem_service, output_repository, youtube_client):
    return MediaService(settings, filesystem_service, output_repository, youtube_client)


def test_download_youtube_video_uses_provided_job_id_for_work_dir(service, output_repository, youtube_client):
    result, work_dir, final_dir = service.download_youtube_video(
        youtube_url="https://youtu.be/example",
        desired_output_name="Custom Output",
        job_id="12345",
    )

    assert output_repository.create_work_dir_calls == ["job-12345"]
    assert youtube_client.download_best_mkv_calls == [
        ("https://youtu.be/example", output_repository.work_dir, "Custom Output")
    ]
    assert output_repository.create_output_dir_calls == ["Movie One"]
    assert result is youtube_client.return_value
    assert work_dir == output_repository.work_dir
    assert final_dir == output_repository.output_dir


def test_download_youtube_video_generates_job_id_when_missing(service, output_repository, youtube_client, monkeypatch):
    monkeypatch.setattr("app.services.media_service.uuid4", lambda: "generated-id")

    result, work_dir, final_dir = service.download_youtube_video(
        youtube_url="https://youtu.be/example",
        desired_output_name=None,
    )

    assert output_repository.create_work_dir_calls == ["job-generated-id"]
    assert youtube_client.download_best_mkv_calls == [
        ("https://youtu.be/example", output_repository.work_dir, None)
    ]
    assert output_repository.create_output_dir_calls == ["Movie One"]
    assert result is youtube_client.return_value
    assert work_dir == output_repository.work_dir
    assert final_dir == output_repository.output_dir


@pytest.mark.parametrize(
    "desired_output_name",
    [None, "", "Movie One", "Custom Output"],
)
def test_download_youtube_video_passes_desired_output_name_through(
    service,
    output_repository,
    youtube_client,
    desired_output_name,
):
    service.download_youtube_video(
        youtube_url="https://youtu.be/example",
        desired_output_name=desired_output_name,
        job_id="abc",
    )

    assert youtube_client.download_best_mkv_calls == [
        ("https://youtu.be/example", output_repository.work_dir, desired_output_name)
    ]


def test_download_youtube_video_uses_download_result_output_name_for_final_dir(
    service,
    output_repository,
    youtube_client,
):
    youtube_client.return_value = DownloadResult(
        title="Different Source Title",
        output_name="Resolved Output Name",
        video_path=Path("/tmp/inprogress/job-abc/Resolved Output Name.mkv"),
        aux_files=[],
    )

    result, work_dir, final_dir = service.download_youtube_video(
        youtube_url="https://youtu.be/example",
        desired_output_name="Ignored For Final Dir",
        job_id="abc",
    )

    assert output_repository.create_output_dir_calls == ["Resolved Output Name"]
    assert result.output_name == "Resolved Output Name"
    assert work_dir == output_repository.work_dir
    assert final_dir == output_repository.output_dir


def test_finalize_video_moves_video_into_output_directory(service, filesystem_service):
    video_path = Path("/tmp/inprogress/job-abc/Movie One.mkv")
    final_dir = Path("/library/output/Movie One")

    result = service.finalize_video(video_path, final_dir)

    assert filesystem_service.move_to_directory_calls == [(video_path, final_dir)]
    assert result == filesystem_service.return_value