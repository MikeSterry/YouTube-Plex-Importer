from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.filesystem_service import FilesystemService


@pytest.fixture()
def settings(tmp_path):
    return SimpleNamespace(
        output_dir=str(tmp_path / "output"),
        inprogress_dir=str(tmp_path / "inprogress"),
        app_dir_mode=0o755,
        app_file_mode=0o644,
    )


@pytest.fixture()
def service(settings):
    return FilesystemService(settings)


def test_ensure_directory_creates_missing_directory(service, tmp_path):
    target = tmp_path / "nested" / "dir"

    assert not target.exists()

    result = service.ensure_directory(target)

    assert result == target
    assert target.exists()
    assert target.is_dir()


def test_ensure_directory_is_idempotent_for_existing_directory(service, tmp_path):
    target = tmp_path / "existing"
    target.mkdir(parents=True)

    result = service.ensure_directory(target)

    assert result == target
    assert target.exists()
    assert target.is_dir()


def test_write_text_creates_file_with_expected_contents(service, tmp_path):
    target = tmp_path / "chapters.txt"
    content = "line 1\nline 2\n"

    result = service.write_text(target, content)

    assert result == target
    assert target.exists()
    assert target.read_text(encoding="utf-8") == content


def test_write_text_overwrites_existing_file(service, tmp_path):
    target = tmp_path / "data.txt"
    target.write_text("old content", encoding="utf-8")

    result = service.write_text(target, "new content")

    assert result == target
    assert target.read_text(encoding="utf-8") == "new content"


def test_write_text_raises_when_parent_directory_missing(service, tmp_path):
    target = tmp_path / "deep" / "nested" / "file.txt"

    with pytest.raises(FileNotFoundError):
        service.write_text(target, "hello world")


def test_normalize_file_preserves_existing_file(service, tmp_path):
    target = tmp_path / "video.mkv"
    target.write_bytes(b"video-bytes")

    result = service.normalize_file(target)

    assert result == target
    assert target.exists()
    assert target.read_bytes() == b"video-bytes"


def test_normalize_file_on_missing_path_raises_file_not_found(service, tmp_path):
    target = tmp_path / "missing.mkv"

    with pytest.raises(FileNotFoundError):
        service.normalize_file(target)

    assert not target.exists()


@pytest.mark.parametrize(
    "relative_path",
    [
        "simple.txt",
        "nested/file.txt",
        "nested/deeper/file.txt",
    ],
)
def test_write_text_handles_existing_parent_path_shapes(service, tmp_path, relative_path):
    target = tmp_path / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    content = f"content for {relative_path}"

    result = service.write_text(target, content)

    assert result == target
    assert target.read_text(encoding="utf-8") == content


@pytest.mark.parametrize(
    "directory_path",
    [
        "one",
        "one/two",
        "one/two/three",
    ],
)
def test_ensure_directory_handles_multiple_path_shapes(service, tmp_path, directory_path):
    target = tmp_path / directory_path

    result = service.ensure_directory(target)

    assert result == target
    assert target.exists()
    assert target.is_dir()