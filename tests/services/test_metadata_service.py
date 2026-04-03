

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.metadata_service import MetadataService


class DummyFilesystemService:
    def __init__(self):
        self.normalize_file_calls = []
        self.return_value = None

    def normalize_file(self, path: Path) -> Path:
        self.normalize_file_calls.append(path)
        return self.return_value or path


@pytest.fixture()
def filesystem_service():
    return DummyFilesystemService()


@pytest.fixture()
def settings():
    return SimpleNamespace(mkvmerge_bin="mkvmerge")


@pytest.fixture()
def service(filesystem_service, settings):
    signature = inspect.signature(MetadataService)
    kwargs = {}

    for name in signature.parameters:
        if name == "self":
            continue
        if name in {"filesystem_service", "filesystem", "fs_service"}:
            kwargs[name] = filesystem_service
        elif name == "settings":
            kwargs[name] = settings
        else:
            kwargs[name] = SimpleNamespace()

    instance = MetadataService(**kwargs)

    for attr_name, value in {
        "_filesystem_service": filesystem_service,
        "filesystem_service": filesystem_service,
        "_settings": settings,
        "settings": settings,
    }.items():
        if hasattr(instance, attr_name):
            setattr(instance, attr_name, value)

    if not hasattr(instance, "_filesystem_service"):
        setattr(instance, "_filesystem_service", filesystem_service)
    if not hasattr(instance, "_settings"):
        setattr(instance, "_settings", settings)

    return instance


def _expected_temp_output(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}.chapters.tmp.mkv")


def test_merge_chapters_runs_mkvmerge_and_returns_normalized_output_path(service, filesystem_service, tmp_path, monkeypatch):
    source_video = tmp_path / "Movie One.mkv"
    chapter_file = tmp_path / "chapter.txt"
    output_path = tmp_path / "Movie One.chapters.mkv"
    source_video.write_text("video", encoding="utf-8")
    chapter_file.write_text("chapters", encoding="utf-8")

    calls = []

    def fake_run_mkvmerge(source_arg: Path, chapter_arg: Path, temp_arg: Path) -> None:
        calls.append((source_arg, chapter_arg, temp_arg))
        temp_arg.write_text("merged-video", encoding="utf-8")

    monkeypatch.setattr(service, "_run_mkvmerge", fake_run_mkvmerge)

    result = service.merge_chapters(source_video, chapter_file, output_path)

    expected_temp = _expected_temp_output(output_path)
    assert calls == [(source_video, chapter_file, expected_temp)]
    assert filesystem_service.normalize_file_calls == [output_path, output_path]
    assert result == output_path
    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8") == "merged-video"
    assert not expected_temp.exists()


def test_merge_chapters_builds_expected_temp_output_name(service, tmp_path, monkeypatch):
    source_video = tmp_path / "source.mkv"
    chapter_file = tmp_path / "chapter.txt"
    output_path = tmp_path / "output.with-chapters.mkv"
    source_video.write_text("video", encoding="utf-8")
    chapter_file.write_text("chapters", encoding="utf-8")

    captured = []

    def fake_run_mkvmerge(source_arg: Path, chapter_arg: Path, temp_arg: Path) -> None:
        captured.append(temp_arg)
        temp_arg.write_text("merged-video", encoding="utf-8")

    monkeypatch.setattr(service, "_run_mkvmerge", fake_run_mkvmerge)

    service.merge_chapters(source_video, chapter_file, output_path)

    assert captured == [output_path.with_name("output.with-chapters.chapters.tmp.mkv")]


def test_merge_chapters_passes_original_source_and_chapter_paths(service, tmp_path, monkeypatch):
    source_video = tmp_path / "nested" / "source.mkv"
    chapter_file = tmp_path / "nested" / "chapter.txt"
    output_path = tmp_path / "nested" / "result.mkv"
    source_video.parent.mkdir(parents=True, exist_ok=True)
    source_video.write_text("video", encoding="utf-8")
    chapter_file.write_text("chapters", encoding="utf-8")

    captured = []

    def fake_run_mkvmerge(source_arg: Path, chapter_arg: Path, temp_arg: Path) -> None:
        captured.append((source_arg, chapter_arg, temp_arg))
        temp_arg.write_text("merged-video", encoding="utf-8")

    monkeypatch.setattr(service, "_run_mkvmerge", fake_run_mkvmerge)

    service.merge_chapters(source_video, chapter_file, output_path)

    assert captured[0][0] is source_video
    assert captured[0][1] is chapter_file
    assert captured[0][2] == _expected_temp_output(output_path)


def test_merge_chapters_returns_normalize_file_result(service, filesystem_service, tmp_path, monkeypatch):
    source_video = tmp_path / "Movie One.mkv"
    chapter_file = tmp_path / "chapter.txt"
    output_path = tmp_path / "Movie One.chapters.mkv"
    source_video.write_text("video", encoding="utf-8")
    chapter_file.write_text("chapters", encoding="utf-8")
    filesystem_service.return_value = tmp_path / "normalized-result.mkv"

    def fake_run_mkvmerge(source_arg: Path, chapter_arg: Path, temp_arg: Path) -> None:
        temp_arg.write_text("merged-video", encoding="utf-8")

    monkeypatch.setattr(service, "_run_mkvmerge", fake_run_mkvmerge)

    result = service.merge_chapters(source_video, chapter_file, output_path)

    assert result == filesystem_service.return_value