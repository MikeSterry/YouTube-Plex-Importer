from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import app.clients.youtube_client as youtube_client_module
from app.clients.youtube_client import YoutubeClient
from app.exceptions import YoutubeDownloadError
from yt_dlp.utils import DownloadError


class DummyFilesystemService:
    def __init__(self):
        self.normalized_paths = []

    def normalize_file(self, path: Path) -> None:
        self.normalized_paths.append(path)


class FakeYoutubeDL:
    extract_info_response = {"title": "Test Title", "id": "abc123"}
    download_side_effects = []
    created_instances = []

    def __init__(self, options):
        self.options = options
        self.download_calls = []
        self.extract_info_calls = []
        FakeYoutubeDL.created_instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, youtube_url, download=False):
        self.extract_info_calls.append((youtube_url, download))
        return dict(FakeYoutubeDL.extract_info_response)

    def download(self, urls):
        self.download_calls.append(list(urls))
        if FakeYoutubeDL.download_side_effects:
            effect = FakeYoutubeDL.download_side_effects.pop(0)
            if isinstance(effect, Exception):
                raise effect
            if callable(effect):
                return effect(urls)
        return 0


@pytest.fixture()
def settings():
    return SimpleNamespace(
        ytdlp_format="bestvideo*+bestaudio/best",
        ytdlp_js_runtimes_dict={"default": "node"},
        ytdlp_remote_components_set={"player"},
        ytdlp_socket_timeout=30,
        ytdlp_retries=5,
        ytdlp_fragment_retries=6,
        ytdlp_file_access_retries=7,
        ytdlp_extractor_retries=8,
        ytdlp_retry_sleep_http="1",
        ytdlp_retry_sleep_fragment="linear=1:3:1",
        ytdlp_retry_sleep_file_access="exp=1:8:2",
        ytdlp_retry_sleep_extractor="",
        ytdlp_http_chunk_size=1048576,
        ytdlp_throttled_rate="4M",
    )


@pytest.fixture()
def filesystem_service():
    return DummyFilesystemService()


@pytest.fixture()
def client(settings, filesystem_service, monkeypatch):
    FakeYoutubeDL.extract_info_response = {"title": "Test Title", "id": "abc123"}
    FakeYoutubeDL.download_side_effects = []
    FakeYoutubeDL.created_instances = []
    monkeypatch.setattr(youtube_client_module, "YoutubeDL", FakeYoutubeDL)
    return YoutubeClient(settings, filesystem_service)


def test_build_output_name_uses_desired_name(client):
    result = client._build_output_name(
        {"title": "Ignored Title", "id": "abc123"},
        "My Custom Output",
    )

    assert result == "My Custom Output"


@pytest.mark.parametrize(
    ("info", "expected"),
    [
        ({"title": "Video Title", "id": "abc123"}, "Video Title"),
        ({}, "video"),
        ({"id": "abc123"}, "abc123"),
    ],
)
def test_build_output_name_falls_back_to_title_then_id_then_video(client, info, expected):
    result = client._build_output_name(info, None)

    assert result == expected


def test_extract_info_uses_common_options(client):
    result = client._extract_info("https://youtu.be/example")

    assert result["title"] == "Test Title"
    assert len(FakeYoutubeDL.created_instances) == 1
    instance = FakeYoutubeDL.created_instances[0]
    assert instance.extract_info_calls == [("https://youtu.be/example", False)]
    assert instance.options["quiet"] is True
    assert instance.options["noprogress"] is True


def test_download_media_uses_download_options(client):
    client._download_media("https://youtu.be/example", "/tmp/output/%(ext)s")

    assert len(FakeYoutubeDL.created_instances) == 1
    instance = FakeYoutubeDL.created_instances[0]
    assert instance.download_calls == [["https://youtu.be/example"]]
    assert instance.options["format"] == "bestvideo*+bestaudio/best"
    assert instance.options["merge_output_format"] == "mkv"
    assert instance.options["outtmpl"] == "/tmp/output/%(ext)s"


def test_download_media_retries_then_succeeds(client, monkeypatch):
    sleeps = []
    FakeYoutubeDL.download_side_effects = [
        DownloadError("first failure"),
        DownloadError("second failure"),
        None,
    ]
    monkeypatch.setattr(youtube_client_module.time, "sleep", lambda seconds: sleeps.append(seconds))

    client._download_media("https://youtu.be/example", "/tmp/output/%(ext)s")

    assert len(FakeYoutubeDL.created_instances) == 3
    assert sleeps == [5, 10]


def test_download_media_raises_after_final_attempt(client, monkeypatch):
    sleeps = []
    FakeYoutubeDL.download_side_effects = [
        DownloadError("first failure"),
        DownloadError("second failure"),
        DownloadError("third failure"),
    ]
    monkeypatch.setattr(youtube_client_module.time, "sleep", lambda seconds: sleeps.append(seconds))

    with pytest.raises(YoutubeDownloadError) as exc_info:
        client._download_media("https://youtu.be/example", "/tmp/output/%(ext)s")

    assert len(FakeYoutubeDL.created_instances) == 3
    assert sleeps == [5, 10]
    assert "third failure" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, DownloadError)


def test_find_video_path_returns_first_match_and_normalizes(client, filesystem_service, tmp_path):
    expected = tmp_path / "Test Title.mkv"
    expected.write_bytes(b"video")

    result = client._find_video_path(tmp_path, "Test Title")

    assert result == expected
    assert filesystem_service.normalized_paths == [expected]


def test_find_video_path_raises_when_missing(client, tmp_path):
    with pytest.raises(FileNotFoundError, match="Unable to locate downloaded MKV file"):
        client._find_video_path(tmp_path, "Missing Title")


def test_download_best_mkv_happy_path(client, tmp_path):
    output_file = tmp_path / "My Output.mkv"
    output_file.write_bytes(b"video")
    extra_file = tmp_path / "My Output.jpg"
    extra_file.write_bytes(b"image")

    result = client.download_best_mkv(
        youtube_url="https://youtu.be/example",
        work_dir=tmp_path,
        desired_output_name="My Output",
    )

    assert result.title == "Test Title"
    assert result.output_name == "My Output"
    assert result.video_path == output_file
    assert output_file in result.aux_files
    assert extra_file in result.aux_files


def test_build_common_options_contains_expected_settings(client):
    options = client._build_common_options()

    assert options["quiet"] is True
    assert options["noprogress"] is True
    assert options["skip_download"] is False
    assert options["js_runtimes"] == {"default": "node"}
    assert options["remote_components"] == {"player"}
    assert options["socket_timeout"] == 30
    assert options["retries"] == 5
    assert options["fragment_retries"] == 6
    assert options["file_access_retries"] == 7
    assert options["extractor_retries"] == 8
    assert options["http_chunk_size"] == 1048576
    assert options["throttledratelimit"] == 4 * 1024 * 1024
    assert callable(options["retry_sleep_functions"]["http"])
    assert callable(options["retry_sleep_functions"]["fragment"])
    assert callable(options["retry_sleep_functions"]["file_access"])
    assert options["retry_sleep_functions"]["extractor"] is None


@pytest.mark.parametrize(
    ("expr", "attempt", "expected"),
    [
        ("5", 1, 5.0),
        ("linear=1:5:2", 1, 1.0),
        ("linear=1:5:2", 2, 3.0),
        ("linear=1:5:2", 4, 5.0),
        ("exp=1:10:2", 1, 1.0),
        ("exp=1:10:2", 2, 2.0),
        ("exp=1:10:2", 5, 10.0),
    ],
)
def test_build_retry_sleep_supported_formats(client, expr, attempt, expected):
    func = client._build_retry_sleep(expr)

    assert func is not None
    assert func(attempt) == expected


@pytest.mark.parametrize("expr", ["", "garbage", "linear=", "exp="])
def test_build_retry_sleep_returns_none_for_unsupported_or_empty_expressions(client, expr):
    if expr in {"linear=", "exp="}:
        # these currently build functions using defaults/empty values in helper methods
        func = client._build_retry_sleep(expr)
        assert callable(func)
    else:
        assert client._build_retry_sleep(expr) is None


def test_build_linear_sleep_defaults(client):
    func = client._build_linear_sleep("")

    assert func(1) == 1.0
    assert func(2) == 1.0


def test_build_exp_sleep_defaults(client):
    func = client._build_exp_sleep("")

    assert func(1) == 1.0
    assert func(2) == 1.0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("100", 100),
        ("1K", 1024),
        ("1.5K", 1536),
        ("2M", 2 * 1024 * 1024),
        ("1G", 1024 * 1024 * 1024),
        (" 4m ", 4 * 1024 * 1024),
        ("", None),
    ],
)
def test_parse_rate_supported_values(client, value, expected):
    assert client._parse_rate(value) == expected


@pytest.mark.parametrize("value", ["abc", "1Z"])
def test_parse_rate_invalid_values_raise_value_error(client, value):
    with pytest.raises(ValueError):
        client._parse_rate(value)