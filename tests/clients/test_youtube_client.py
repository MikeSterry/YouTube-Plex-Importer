from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from yt_dlp.utils import DownloadError

from app.clients import youtube_client as youtube_client_module
from app.clients.youtube_client import YoutubeClient
from app.exceptions import YoutubeDownloadError


class DummyFilesystemService:
    def __init__(self) -> None:
        self.normalized_paths: list[Path] = []

    def normalize_file(self, path: Path) -> None:
        self.normalized_paths.append(path)


class DummySettingsService:
    def __init__(self, cookie_file_path: str | None = None) -> None:
        self.cookie_file_path = cookie_file_path

    def get_youtube_cookie_file_path(self) -> str | None:
        return self.cookie_file_path


class FakeYoutubeDL:
    extract_info_response = {"title": "Test Title", "id": "abc123"}
    download_side_effects = []
    created_instances = []

    def __init__(self, options):
        self.options = options
        FakeYoutubeDL.created_instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, url, download=False):
        return FakeYoutubeDL.extract_info_response

    def download(self, urls):
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
        ytdlp_remote_components_set={"ejs"},
        ytdlp_socket_timeout=30,
        ytdlp_retries=5,
        ytdlp_fragment_retries=5,
        ytdlp_file_access_retries=3,
        ytdlp_extractor_retries=2,
        ytdlp_retry_sleep_http="linear=1:3:1",
        ytdlp_retry_sleep_fragment="exp=1:8:2",
        ytdlp_retry_sleep_file_access="exp=1:8:2",
        ytdlp_retry_sleep_extractor="",
        ytdlp_http_chunk_size=1048576,
        ytdlp_throttled_rate="4M",
    )


@pytest.fixture()
def filesystem_service():
    return DummyFilesystemService()


@pytest.fixture()
def settings_service():
    return DummySettingsService()


@pytest.fixture()
def client(settings, filesystem_service, settings_service, monkeypatch):
    FakeYoutubeDL.extract_info_response = {"title": "Test Title", "id": "abc123"}
    FakeYoutubeDL.download_side_effects = []
    FakeYoutubeDL.created_instances = []
    monkeypatch.setattr(youtube_client_module, "YoutubeDL", FakeYoutubeDL)
    return YoutubeClient(settings, filesystem_service, settings_service)


def test_build_output_name_uses_desired_output_name(client):
    info = {"title": "Ignored Title", "id": "abc123"}

    result = client._build_output_name(info, "My Custom Name")

    assert result == "My Custom Name"


def test_build_output_name_uses_title_when_desired_name_missing(client):
    info = {"title": "Test Title", "id": "abc123"}

    result = client._build_output_name(info, None)

    assert result == "Test Title"


def test_build_output_name_uses_id_when_title_missing(client):
    info = {"id": "abc123"}

    result = client._build_output_name(info, None)

    assert result == "abc123"


def test_build_output_name_uses_video_when_title_and_id_missing(client):
    info = {}

    result = client._build_output_name(info, None)

    assert result == "video"


def test_extract_info_uses_youtubedl_and_returns_metadata(client):
    result = client._extract_info("https://youtube.com/watch?v=abc123")

    assert result == {"title": "Test Title", "id": "abc123"}
    assert len(FakeYoutubeDL.created_instances) == 1
    assert FakeYoutubeDL.created_instances[0].options["quiet"] is True
    assert FakeYoutubeDL.created_instances[0].options["noprogress"] is True


def test_build_common_options_without_cookiefile(client):
    options = client._build_common_options()

    assert options["quiet"] is True
    assert options["noprogress"] is True
    assert options["skip_download"] is False
    assert options["js_runtimes"] == {"default": "node"}
    assert options["remote_components"] == {"ejs"}
    assert options["socket_timeout"] == 30
    assert options["retries"] == 5
    assert options["fragment_retries"] == 5
    assert options["file_access_retries"] == 3
    assert options["extractor_retries"] == 2
    assert options["http_chunk_size"] == 1048576
    assert options["throttledratelimit"] == 4 * 1024 * 1024
    assert "cookiefile" not in options


def test_build_common_options_with_cookiefile(settings, filesystem_service, monkeypatch):
    FakeYoutubeDL.extract_info_response = {"title": "Test Title", "id": "abc123"}
    FakeYoutubeDL.download_side_effects = []
    FakeYoutubeDL.created_instances = []
    monkeypatch.setattr(youtube_client_module, "YoutubeDL", FakeYoutubeDL)

    settings_service = DummySettingsService("/data/youtube_cookies.txt")
    client = YoutubeClient(settings, filesystem_service, settings_service)

    options = client._build_common_options()

    assert options["cookiefile"] == "/data/youtube_cookies.txt"


def test_parse_rate_supports_plain_integer(client):
    assert client._parse_rate("1024") == 1024


def test_parse_rate_supports_kilobytes(client):
    assert client._parse_rate("10K") == 10 * 1024


def test_parse_rate_supports_megabytes(client):
    assert client._parse_rate("4M") == 4 * 1024 * 1024


def test_parse_rate_supports_gigabytes(client):
    assert client._parse_rate("2G") == 2 * 1024 * 1024 * 1024


def test_parse_rate_returns_none_when_empty(client):
    assert client._parse_rate("") is None
    assert client._parse_rate(None) is None


def test_build_retry_sleep_returns_none_for_empty_expression(client):
    assert client._build_retry_sleep("") is None
    assert client._build_retry_sleep(None) is None


def test_build_retry_sleep_with_fixed_seconds(client):
    sleep_fn = client._build_retry_sleep("5")

    assert sleep_fn(1) == 5.0
    assert sleep_fn(99) == 5.0


def test_build_linear_sleep(client):
    sleep_fn = client._build_linear_sleep("1:5:2")

    assert sleep_fn(1) == 1.0
    assert sleep_fn(2) == 3.0
    assert sleep_fn(3) == 5.0
    assert sleep_fn(4) == 5.0


def test_build_exp_sleep(client):
    sleep_fn = client._build_exp_sleep("1:8:2")

    assert sleep_fn(1) == 1.0
    assert sleep_fn(2) == 2.0
    assert sleep_fn(3) == 4.0
    assert sleep_fn(4) == 8.0
    assert sleep_fn(5) == 8.0


def test_find_video_path_returns_matching_mkv_and_normalizes(tmp_path, client, filesystem_service):
    target = tmp_path / "Test Title.mkv"
    target.write_text("video")

    result = client._find_video_path(tmp_path, "Test Title")

    assert result == target
    assert filesystem_service.normalized_paths == [target]


def test_find_video_path_raises_when_missing(tmp_path, client):
    with pytest.raises(FileNotFoundError, match="Unable to locate downloaded MKV file"):
        client._find_video_path(tmp_path, "Missing Title")


def test_download_best_mkv_returns_download_result(tmp_path, client):
    output_file = tmp_path / "My Output.mkv"
    output_file.write_text("video")

    result = client.download_best_mkv(
        "https://youtube.com/watch?v=abc123",
        tmp_path,
        desired_output_name="My Output",
    )

    assert result.title == "Test Title"
    assert result.output_name == "My Output"
    assert result.video_path == output_file
    assert output_file in result.aux_files


def test_download_media_passes_format_options(tmp_path, client):
    output_file = tmp_path / "Test Title.mkv"
    output_file.write_text("video")

    client._download_media(
        "https://youtube.com/watch?v=abc123",
        str(tmp_path / "Test Title.%(ext)s"),
    )

    assert len(FakeYoutubeDL.created_instances) == 1
    options = FakeYoutubeDL.created_instances[0].options
    assert options["format"] == "bestvideo*+bestaudio/best"
    assert options["merge_output_format"] == "mkv"
    assert options["outtmpl"] == str(tmp_path / "Test Title.%(ext)s")


def test_download_media_retries_and_succeeds(tmp_path, client, monkeypatch):
    sleep_calls = []
    monkeypatch.setattr(youtube_client_module.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    FakeYoutubeDL.download_side_effects = [
        DownloadError("temporary failure"),
        None,
    ]

    client._download_media(
        "https://youtube.com/watch?v=abc123",
        str(tmp_path / "Test Title.%(ext)s"),
    )

    assert len(FakeYoutubeDL.created_instances) == 2
    assert sleep_calls == [5]


def test_download_media_raises_youtube_download_error_after_retries(tmp_path, client, monkeypatch):
    sleep_calls = []
    monkeypatch.setattr(youtube_client_module.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    FakeYoutubeDL.download_side_effects = [
        DownloadError("failure 1"),
        DownloadError("failure 2"),
        DownloadError("failure 3"),
    ]

    with pytest.raises(YoutubeDownloadError, match="failure 3"):
        client._download_media(
            "https://youtube.com/watch?v=abc123",
            str(tmp_path / "Test Title.%(ext)s"),
        )

    assert sleep_calls == [5, 10]
    assert len(FakeYoutubeDL.created_instances) == 3


def test_download_media_appends_settings_hint_when_bot_error_and_no_cookies(
    settings,
    filesystem_service,
    monkeypatch,
    tmp_path,
):
    sleep_calls = []
    monkeypatch.setattr(youtube_client_module.time, "sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr(youtube_client_module, "YoutubeDL", FakeYoutubeDL)

    FakeYoutubeDL.download_side_effects = [
        DownloadError("Sign in to confirm you’re not a bot"),
        DownloadError("Sign in to confirm you’re not a bot"),
        DownloadError("Sign in to confirm you’re not a bot"),
    ]
    FakeYoutubeDL.created_instances = []

    client = YoutubeClient(settings, filesystem_service, DummySettingsService(None))

    with pytest.raises(YoutubeDownloadError) as exc_info:
        client._download_media(
            "https://youtube.com/watch?v=abc123",
            str(tmp_path / "Test Title.%(ext)s"),
        )

    assert "Configure YouTube cookies on the Settings page and try again." in str(exc_info.value)
    assert sleep_calls == [5, 10]


def test_download_media_does_not_append_settings_hint_when_cookiefile_exists(
    settings,
    filesystem_service,
    monkeypatch,
    tmp_path,
):
    sleep_calls = []
    monkeypatch.setattr(youtube_client_module.time, "sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr(youtube_client_module, "YoutubeDL", FakeYoutubeDL)

    FakeYoutubeDL.download_side_effects = [
        DownloadError("Sign in to confirm you’re not a bot"),
        DownloadError("Sign in to confirm you’re not a bot"),
        DownloadError("Sign in to confirm you’re not a bot"),
    ]
    FakeYoutubeDL.created_instances = []

    client = YoutubeClient(
        settings,
        filesystem_service,
        DummySettingsService("/data/youtube_cookies.txt"),
    )

    with pytest.raises(YoutubeDownloadError) as exc_info:
        client._download_media(
            "https://youtube.com/watch?v=abc123",
            str(tmp_path / "Test Title.%(ext)s"),
        )

    assert "Configure YouTube cookies on the Settings page and try again." not in str(exc_info.value)
    assert sleep_calls == [5, 10]