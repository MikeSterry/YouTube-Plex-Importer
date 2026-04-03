from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.repositories.output_repository import OutputRepository


class DummyFilesystemService:
    def __init__(self):
        self.ensure_directory_calls = []

    def ensure_directory(self, path: Path) -> None:
        self.ensure_directory_calls.append(path)


@pytest.fixture()
def settings(tmp_path):
    return SimpleNamespace(
        output_dir=str(tmp_path / "output"),
        inprogress_dir=str(tmp_path / "inprogress"),
    )


@pytest.fixture()
def filesystem_service():
    return DummyFilesystemService()


@pytest.fixture()
def repository(settings, filesystem_service):
    return OutputRepository(settings, filesystem_service)


def test_init_ensures_base_directories(settings, filesystem_service):
    OutputRepository(settings, filesystem_service)

    assert filesystem_service.ensure_directory_calls == [
        Path(settings.output_dir),
        Path(settings.inprogress_dir),
    ]


def test_create_work_dir_creates_and_returns_inprogress_path(repository, filesystem_service, settings):
    result = repository.create_work_dir("My Output")

    expected = Path(settings.inprogress_dir) / "My Output"
    assert result == expected
    assert filesystem_service.ensure_directory_calls[-1] == expected


def test_create_output_dir_creates_and_returns_output_path(repository, filesystem_service, settings):
    result = repository.create_output_dir("My Output")

    expected = Path(settings.output_dir) / "My Output"
    assert result == expected
    assert filesystem_service.ensure_directory_calls[-1] == expected


def test_list_outputs_returns_relative_paths_and_sorted_files(repository, tmp_path):
    base = Path(repository._settings.output_dir)
    movie_dir = base / "Movies" / "Movie One"
    nested_dir = base / "Shows" / "Show A"

    movie_dir.mkdir(parents=True)
    nested_dir.mkdir(parents=True)

    (movie_dir / "b-file.jpg").write_text("b", encoding="utf-8")
    (movie_dir / "a-file.mkv").write_text("a", encoding="utf-8")
    (movie_dir / "ignore-dir").mkdir()

    (nested_dir / "poster.png").write_text("poster", encoding="utf-8")
    (nested_dir / "video.mkv").write_text("video", encoding="utf-8")

    result = repository.list_outputs()

    assert [(entry.name, entry.path, entry.files) for entry in result] == [
        ("Movies", "Movies", []),
        ("Movies/Movie One", "Movies/Movie One", ["a-file.mkv", "b-file.jpg"]),
        ("Movies/Movie One/ignore-dir", "Movies/Movie One/ignore-dir", []),
        ("Shows", "Shows", []),
        ("Shows/Show A", "Shows/Show A", ["poster.png", "video.mkv"]),
    ]


def test_list_poster_files_returns_only_supported_images(repository):
    output_dir = Path(repository._settings.output_dir) / "Movie One"
    output_dir.mkdir(parents=True)

    (output_dir / "poster.jpg").write_text("jpg", encoding="utf-8")
    (output_dir / "cover.jpeg").write_text("jpeg", encoding="utf-8")
    (output_dir / "art.png").write_text("png", encoding="utf-8")
    (output_dir / "video.mkv").write_text("video", encoding="utf-8")
    (output_dir / "notes.txt").write_text("notes", encoding="utf-8")
    (output_dir / "subdir").mkdir()

    result = repository.list_poster_files("Movie One")

    assert result == ["art.png", "cover.jpeg", "poster.jpg"]


def test_find_update_target_returns_directory_and_primary_video(repository):
    output_dir = Path(repository._settings.output_dir) / "Movie One"
    output_dir.mkdir(parents=True)

    first_video = output_dir / "a-video.mkv"
    second_video = output_dir / "b-video.mp4"
    (output_dir / "poster.jpg").write_text("poster", encoding="utf-8")
    first_video.write_text("video-a", encoding="utf-8")
    second_video.write_text("video-b", encoding="utf-8")

    result = repository.find_update_target("Movie One")

    assert result.output_name == "Movie One"
    assert result.directory == output_dir.resolve()
    assert result.mkv_path == first_video


def test_find_update_target_returns_none_video_when_no_video_exists(repository):
    output_dir = Path(repository._settings.output_dir) / "Movie One"
    output_dir.mkdir(parents=True)
    (output_dir / "poster.jpg").write_text("poster", encoding="utf-8")

    result = repository.find_update_target("Movie One")

    assert result.output_name == "Movie One"
    assert result.directory == output_dir.resolve()
    assert result.mkv_path is None


def test_resolve_poster_file_returns_valid_image(repository):
    output_dir = Path(repository._settings.output_dir) / "Movie One"
    output_dir.mkdir(parents=True)
    poster = output_dir / "poster.jpg"
    poster.write_text("poster", encoding="utf-8")

    result = repository.resolve_poster_file("Movie One", "poster.jpg")

    assert result == poster.resolve()


def test_resolve_poster_file_rejects_missing_file(repository):
    output_dir = Path(repository._settings.output_dir) / "Movie One"
    output_dir.mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="Poster file not found: missing.jpg"):
        repository.resolve_poster_file("Movie One", "missing.jpg")


def test_resolve_poster_file_rejects_non_image_file(repository):
    output_dir = Path(repository._settings.output_dir) / "Movie One"
    output_dir.mkdir(parents=True)
    file_path = output_dir / "notes.txt"
    file_path.write_text("notes", encoding="utf-8")

    with pytest.raises(ValueError, match="Poster file must be png, jpg, or jpeg."):
        repository.resolve_poster_file("Movie One", "notes.txt")


def test_resolve_poster_file_rejects_path_traversal(repository):
    output_dir = Path(repository._settings.output_dir) / "Movie One"
    output_dir.mkdir(parents=True)

    outside_file = Path(repository._settings.output_dir).parent / "outside.jpg"
    outside_file.write_text("outside", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="Poster file not found: ../outside.jpg"):
        repository.resolve_poster_file("Movie One", "../outside.jpg")


def test_resolve_output_dir_finds_direct_match(repository):
    output_dir = Path(repository._settings.output_dir) / "Movies" / "Movie One"
    output_dir.mkdir(parents=True)

    result = repository._resolve_output_dir("Movies/Movie One")

    assert result == output_dir.resolve()


def test_resolve_output_dir_finds_match_by_leaf_name_when_unique(repository):
    output_dir = Path(repository._settings.output_dir) / "Movies" / "Movie One"
    output_dir.mkdir(parents=True)

    result = repository._resolve_output_dir("Movie One")

    assert result == output_dir.resolve()


def test_resolve_output_dir_uses_normalized_lookup(repository):
    output_dir = Path(repository._settings.output_dir) / "Movies" / "Movie One"
    output_dir.mkdir(parents=True)

    result = repository._resolve_output_dir("Movies%2FMovie%20One")

    assert result == output_dir.resolve()


def test_resolve_output_dir_raises_when_missing(repository):
    with pytest.raises(FileNotFoundError, match="Output directory not found: Missing"):
        repository._resolve_output_dir("Missing")


def test_resolve_output_dir_raises_when_leaf_name_is_ambiguous(repository):
    first_dir = Path(repository._settings.output_dir) / "Movies" / "Shared Name"
    second_dir = Path(repository._settings.output_dir) / "Shows" / "Shared Name"
    first_dir.mkdir(parents=True)
    second_dir.mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="Output directory not found: Shared Name"):
        repository._resolve_output_dir("Shared Name")


def test_iter_output_directories_returns_sorted_relative_order(repository):
    base = Path(repository._settings.output_dir)
    (base / "z-last").mkdir(parents=True)
    (base / "A-first").mkdir(parents=True)
    (base / "mid" / "Nested").mkdir(parents=True)

    result = list(repository._iter_output_directories(base))

    assert [path.relative_to(base).as_posix() for path in result] == [
        "A-first",
        "mid",
        "mid/Nested",
        "z-last",
    ]


def test_find_directory_match_matches_normalized_relative_path(repository):
    base = Path(repository._settings.output_dir)
    target = base / "Movies" / "My Movie"
    target.mkdir(parents=True)

    result = repository._find_directory_match(base, "movies/my movie")

    assert result == target.resolve()


def test_find_directory_match_matches_normalized_leaf_name(repository):
    base = Path(repository._settings.output_dir)
    target = base / "Movies" / "My Movie"
    target.mkdir(parents=True)

    result = repository._find_directory_match(base, "my_movie")

    assert result == target.resolve()


def test_find_directory_match_returns_none_when_ambiguous(repository):
    base = Path(repository._settings.output_dir)
    (base / "Movies" / "Same Name").mkdir(parents=True)
    (base / "Shows" / "Same Name").mkdir(parents=True)

    result = repository._find_directory_match(base, "Same Name")

    assert result is None


def test_safe_join_returns_child_path_when_valid(repository):
    base = Path(repository._settings.output_dir).resolve()
    result = repository._safe_join(base, "Movies/Movie One")

    assert result == (base / "Movies/Movie One").resolve()


@pytest.mark.parametrize("relative_name", ["", ".", "..", "../escape"])
def test_safe_join_rejects_base_or_parent_escape(repository, relative_name):
    base = Path(repository._settings.output_dir).resolve()

    result = repository._safe_join(base, relative_name)

    assert result is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" Movie One ", "Movie One"),
        ("Movies\\Movie One", "Movies/Movie One"),
        ("Movies/Movie One/", "Movies/Movie One"),
        ("Movies%2FMovie%20One", "Movies/Movie One"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_lookup_value(repository, value, expected):
    assert repository._normalize_lookup_value(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Movie One", "movie one"),
        ("movie_one", "movie one"),
        ("movie-one", "movie - one"),
        (" Movies%2FMovie_One ", "movies/movie one"),
    ],
)
def test_normalize_compare_value(repository, value, expected):
    assert repository._normalize_compare_value(value) == expected


def test_find_primary_mkv_returns_first_matching_video_file(repository):
    directory = Path(repository._settings.output_dir) / "Movie One"
    directory.mkdir(parents=True)

    first_video = directory / "a-video.mkv"
    second_video = directory / "b-video.mp4"
    (directory / "notes.txt").write_text("notes", encoding="utf-8")
    second_video.write_text("video-b", encoding="utf-8")
    first_video.write_text("video-a", encoding="utf-8")

    result = repository._find_primary_mkv(directory)

    assert result == first_video


def test_find_primary_mkv_returns_none_when_no_video_file_exists(repository):
    directory = Path(repository._settings.output_dir) / "Movie One"
    directory.mkdir(parents=True)
    (directory / "poster.jpg").write_text("poster", encoding="utf-8")

    result = repository._find_primary_mkv(directory)

    assert result is None


@pytest.mark.parametrize(
    ("file_name", "expected"),
    [
        ("poster.jpg", True),
        ("poster.jpeg", True),
        ("poster.png", True),
        ("poster.txt", False),
    ],
)
def test_is_editable_image_checks_file_extension(repository, file_name, expected):
    directory = Path(repository._settings.output_dir) / "Movie One"
    directory.mkdir(parents=True)
    path = directory / file_name
    path.write_text("content", encoding="utf-8")

    assert repository._is_editable_image(path) is expected


def test_is_editable_image_rejects_directories(repository):
    directory = Path(repository._settings.output_dir) / "Movie One"
    directory.mkdir(parents=True)

    assert repository._is_editable_image(directory) is False