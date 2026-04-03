from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from app.models.domain import PosterCropSettings
from app.services.image_service import ImageService
from app.utils.constants import BACKGROUND_FILENAME, POSTER_FILENAME


class DummyFilesystemService:
    def __init__(self):
        self.ensure_directory_calls = []
        self.normalize_file_calls = []

    def ensure_directory(self, path: Path) -> Path:
        self.ensure_directory_calls.append(path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def normalize_file(self, path: Path) -> Path:
        self.normalize_file_calls.append(path)
        return path


class DummyHttpClient:
    def __init__(self):
        self.get_bytes_calls = []
        self.responses = {}

    def get_bytes(self, image_url: str) -> bytes:
        self.get_bytes_calls.append(image_url)
        return self.responses[image_url]


@pytest.fixture()
def settings():
    return SimpleNamespace()


@pytest.fixture()
def filesystem_service():
    return DummyFilesystemService()


@pytest.fixture()
def http_client():
    return DummyHttpClient()


@pytest.fixture()
def service(settings, filesystem_service, http_client):
    return ImageService(settings, filesystem_service, http_client)


def make_image_bytes(size=(800, 1200), image_format="JPEG", color=(120, 30, 200)) -> bytes:
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def open_image_bytes(image_bytes: bytes) -> Image.Image:
    return Image.open(BytesIO(image_bytes))


def test_process_poster_downloads_renders_and_saves_jpeg(service, filesystem_service, http_client, tmp_path):
    image_url = "https://image.test/poster.jpg"
    http_client.responses[image_url] = make_image_bytes(size=(1000, 1500), image_format="JPEG")
    crop_settings = PosterCropSettings(zoom=1.1, offset_x=0.25, offset_y=0.75, mode="cover")

    result = service.process_poster(image_url, tmp_path, crop_settings)

    expected_path = tmp_path / POSTER_FILENAME
    assert http_client.get_bytes_calls == [image_url]
    assert filesystem_service.ensure_directory_calls == [tmp_path]
    assert filesystem_service.normalize_file_calls == [expected_path]
    assert result.source_url == image_url
    assert result.saved_path == expected_path
    assert result.width == 1000
    assert result.height == 1500
    assert expected_path.exists()
    saved = Image.open(expected_path)
    assert saved.format == "JPEG"
    assert saved.size == (1000, 1500)


def test_process_local_poster_renders_and_overwrites_existing_file(service, filesystem_service, tmp_path):
    poster_path = tmp_path / "poster.jpg"
    poster_path.write_bytes(make_image_bytes(size=(500, 500), image_format="JPEG"))
    crop_settings = PosterCropSettings(zoom=1.0, offset_x=0.5, offset_y=0.5, mode="contain")

    result = service.process_local_poster(poster_path, crop_settings)

    assert filesystem_service.ensure_directory_calls == [tmp_path]
    assert filesystem_service.normalize_file_calls == [poster_path]
    assert result.source_url == str(poster_path)
    assert result.saved_path == poster_path
    assert result.width == 600
    assert result.height == 900
    saved = Image.open(poster_path)
    assert saved.format == "JPEG"
    assert saved.size == (600, 900)


def test_process_background_downloads_fits_and_saves_background(service, filesystem_service, http_client, tmp_path):
    image_url = "https://image.test/background.png"
    http_client.responses[image_url] = make_image_bytes(size=(800, 600), image_format="PNG")

    result = service.process_background(image_url, tmp_path)

    expected_path = tmp_path / BACKGROUND_FILENAME
    assert http_client.get_bytes_calls == [image_url]
    assert filesystem_service.ensure_directory_calls == [tmp_path]
    assert filesystem_service.normalize_file_calls == [expected_path]
    assert result.source_url == image_url
    assert result.saved_path == expected_path
    assert result.width == 1280
    assert result.height == 720
    saved = Image.open(expected_path)
    assert saved.format == "JPEG"
    assert saved.size == (1280, 720)


@pytest.mark.parametrize(
    ("image_size", "expected"),
    [
        ((600, 900), "Poster dimensions meet the 600x900 recommendation."),
        ((599, 900), "Poster is below the recommended 600x900 size and may distort."),
        ((600, 899), "Poster is below the recommended 600x900 size and may distort."),
    ],
)
def test_validate_poster_recommendation(service, http_client, image_size, expected):
    image_url = f"https://image.test/{image_size[0]}x{image_size[1]}.jpg"
    http_client.responses[image_url] = make_image_bytes(size=image_size, image_format="JPEG")

    assert service.validate_poster_recommendation(image_url) == expected


def test_build_poster_preview_bytes_returns_jpeg_bytes(service, http_client):
    image_url = "https://image.test/poster.jpg"
    http_client.responses[image_url] = make_image_bytes(size=(500, 500), image_format="JPEG")

    result = service.build_poster_preview_bytes(image_url, PosterCropSettings(mode="contain"))

    preview = open_image_bytes(result)
    assert preview.format == "JPEG"
    assert preview.size == (600, 900)


def test_build_local_poster_preview_bytes_returns_jpeg_bytes(service, tmp_path):
    poster_path = tmp_path / "poster.png"
    poster_path.write_bytes(make_image_bytes(size=(700, 1000), image_format="PNG"))

    result = service.build_local_poster_preview_bytes(poster_path, PosterCropSettings(mode="cover"))

    preview = open_image_bytes(result)
    assert preview.format == "JPEG"
    assert preview.size == (700, 1050)


def test_fetch_source_bytes_returns_original_bytes_and_png_content_type(service, http_client):
    image_url = "https://image.test/art.png"
    image_bytes = make_image_bytes(size=(640, 480), image_format="PNG")
    http_client.responses[image_url] = image_bytes

    result_bytes, content_type = service.fetch_source_bytes(image_url)

    assert result_bytes == image_bytes
    assert content_type == "image/png"


def test_fetch_local_source_bytes_returns_original_bytes_and_jpeg_content_type(service, tmp_path):
    poster_path = tmp_path / "poster.jpg"
    image_bytes = make_image_bytes(size=(640, 480), image_format="JPEG")
    poster_path.write_bytes(image_bytes)

    result_bytes, content_type = service.fetch_local_source_bytes(poster_path)

    assert result_bytes == image_bytes
    assert content_type == "image/jpeg"


@pytest.mark.parametrize(
    "extension",
    [".gif", ".webp", ".txt", ""],
)
def test_validate_extension_rejects_unsupported_types(service, extension):
    with pytest.raises(ValueError, match="Image must use png, jpg, or jpeg."):
        service._validate_extension(extension)


@pytest.mark.parametrize(
    ("extension", "expected"),
    [
        (".png", "image/png"),
        (".jpg", "image/jpeg"),
        (".jpeg", "image/jpeg"),
    ],
)
def test_content_type_maps_extensions(service, extension, expected):
    assert service._content_type(extension) == expected


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (-1.0, 0.0),
        (0.0, 0.0),
        (0.25, 0.25),
        (1.0, 1.0),
        (2.0, 1.0),
    ],
)
def test_normalize_offset_clamps_into_zero_to_one_range(service, offset, expected):
    assert service._normalize_offset(offset) == expected


def test_render_cover_returns_expected_canvas_size(service):
    source = Image.new("RGB", (500, 500), (255, 0, 0))

    result = service._render_poster(source, PosterCropSettings(mode="cover"))

    assert result.size == (600, 900)


def test_render_contain_returns_expected_canvas_size_with_black_padding(service):
    source = Image.new("RGB", (500, 500), (0, 255, 0))

    result = service._render_poster(source, PosterCropSettings(mode="contain"))

    assert result.size == (600, 900)
    assert result.getpixel((0, 0)) == (0, 0, 0)


def test_save_image_uses_png_when_target_suffix_is_png(service, filesystem_service, tmp_path):
    image = Image.new("RGB", (640, 480), (10, 20, 30))
    target = tmp_path / "poster.png"

    result = service._save_image(image, target, source_url="local")

    assert filesystem_service.ensure_directory_calls == [tmp_path]
    assert filesystem_service.normalize_file_calls == [target]
    assert result.source_url == "local"
    assert result.saved_path == target
    assert result.width == 640
    assert result.height == 480
    saved = Image.open(target)
    assert saved.format == "PNG"


def test_open_local_image_rejects_unsupported_extension(service, tmp_path):
    bad_path = tmp_path / "poster.gif"
    bad_path.write_bytes(b"gif")

    with pytest.raises(ValueError, match="Image must use png, jpg, or jpeg."):
        service._open_local_image(bad_path)