from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.job_cleanup_service import JobCleanupService


class DummyFilesystemService:
    def __init__(self):
        self.remove_directory_calls = []

    def remove_directory(self, path: Path) -> None:
        self.remove_directory_calls.append(path)


@pytest.fixture()
def settings(tmp_path):
    return SimpleNamespace(
        inprogress_dir=str(tmp_path / "inprogress"),
        output_dir=str(tmp_path / "output"),
    )


@pytest.fixture()
def filesystem_service():
    return DummyFilesystemService()


@pytest.fixture()
def service(settings, filesystem_service):
    return JobCleanupService(settings, filesystem_service)


def test_cleanup_failed_job_artifacts_removes_work_dir_when_present(service, filesystem_service, settings):
    metadata = {
        "work_dir_name": "job-123",
        "job_type": "update",
        "output_name": "Movie One",
    }

    service.cleanup_failed_job_artifacts(metadata)

    assert filesystem_service.remove_directory_calls == [
        (Path(settings.inprogress_dir) / "job-123").resolve(),
    ]


def test_cleanup_failed_job_artifacts_removes_work_dir_and_create_output(service, filesystem_service, settings):
    metadata = {
        "work_dir_name": "job-123",
        "job_type": "create",
        "output_name": "Movie One",
    }

    service.cleanup_failed_job_artifacts(metadata)

    assert filesystem_service.remove_directory_calls == [
        (Path(settings.inprogress_dir) / "job-123").resolve(),
        (Path(settings.output_dir) / "Movie One").resolve(),
    ]


@pytest.mark.parametrize(
    "job_type",
    ["update", "retry", "delete", "", "unknown"],
)
def test_cleanup_failed_job_artifacts_does_not_remove_output_for_non_create_jobs(
    service,
    filesystem_service,
    settings,
    job_type,
):
    metadata = {
        "work_dir_name": "job-123",
        "job_type": job_type,
        "output_name": "Movie One",
    }

    service.cleanup_failed_job_artifacts(metadata)

    assert filesystem_service.remove_directory_calls == [
        (Path(settings.inprogress_dir) / "job-123").resolve(),
    ]


@pytest.mark.parametrize(
    "work_dir_name",
    [None, "", "   "],
)
def test_cleanup_failed_job_artifacts_skips_missing_work_dir_name(
    service,
    filesystem_service,
    settings,
    work_dir_name,
):
    metadata = {
        "work_dir_name": work_dir_name,
        "job_type": "create",
        "output_name": "Movie One",
    }

    service.cleanup_failed_job_artifacts(metadata)

    assert filesystem_service.remove_directory_calls == [
        (Path(settings.output_dir) / "Movie One").resolve(),
    ]


@pytest.mark.parametrize(
    "output_name",
    [None, "", "   "],
)
def test_cleanup_failed_job_artifacts_skips_missing_output_name_for_create(
    service,
    filesystem_service,
    settings,
    output_name,
):
    metadata = {
        "work_dir_name": "job-123",
        "job_type": "create",
        "output_name": output_name,
    }

    service.cleanup_failed_job_artifacts(metadata)

    assert filesystem_service.remove_directory_calls == [
        (Path(settings.inprogress_dir) / "job-123").resolve(),
    ]


def test_cleanup_failed_job_artifacts_trims_and_normalizes_job_type(service, filesystem_service, settings):
    metadata = {
        "work_dir_name": "  job-123  ",
        "job_type": "  CREATE  ",
        "output_name": "  Movie One  ",
    }

    service.cleanup_failed_job_artifacts(metadata)

    assert filesystem_service.remove_directory_calls == [
        (Path(settings.inprogress_dir) / "job-123").resolve(),
        (Path(settings.output_dir) / "Movie One").resolve(),
    ]


def test_cleanup_failed_job_artifacts_skips_unsafe_work_dir_path_traversal(service, filesystem_service):
    metadata = {
        "work_dir_name": "../escape",
        "job_type": "update",
        "output_name": "Movie One",
    }

    service.cleanup_failed_job_artifacts(metadata)

    assert filesystem_service.remove_directory_calls == []


def test_cleanup_failed_job_artifacts_skips_unsafe_output_path_traversal(service, filesystem_service, settings):
    metadata = {
        "work_dir_name": "job-123",
        "job_type": "create",
        "output_name": "../escape",
    }

    service.cleanup_failed_job_artifacts(metadata)

    assert filesystem_service.remove_directory_calls == [
        (Path(settings.inprogress_dir) / "job-123").resolve(),
    ]


@pytest.mark.parametrize(
    ("base_name", "relative_name"),
    [
        ("inprogress", "child"),
        ("output", "nested/child"),
    ],
)
def test_safe_join_returns_resolved_child_path(service, settings, base_name, relative_name):
    base = Path(getattr(settings, f"{base_name}_dir"))

    result = service._safe_join(base, relative_name)

    assert result == (base / relative_name).resolve()


@pytest.mark.parametrize(
    "relative_name",
    [
        "",
        ".",
        "..",
        "../escape",
        "nested/../../escape",
    ],
)
def test_safe_join_returns_none_for_base_or_parent_escape(service, settings, relative_name):
    base = Path(settings.inprogress_dir)

    result = service._safe_join(base, relative_name)

    assert result is None