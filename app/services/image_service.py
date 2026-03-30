"""Artwork download, processing, and poster preview logic."""

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from app.models.domain import ArtworkResult, PosterCropSettings
from app.utils.constants import (
    ALLOWED_IMAGE_EXTENSIONS,
    BACKGROUND_FILENAME,
    BACKGROUND_RATIO,
    POSTER_FILENAME,
    POSTER_MIN_HEIGHT,
    POSTER_MIN_WIDTH,
    POSTER_RATIO,
)
from app.utils.file_utils import FileNameUtils


class ImageService:
    """Download, validate, transform, and store artwork files."""

    def __init__(self, settings, filesystem_service, http_client) -> None:
        """Store shared dependencies for image operations."""
        self._settings = settings
        self._filesystem_service = filesystem_service
        self._http_client = http_client

    def process_poster(
        self,
        image_url: str,
        destination_dir: Path,
        crop_settings: PosterCropSettings | None = None,
    ) -> ArtworkResult:
        """Download and save a poster using the configured crop settings."""
        image = self._download_image(image_url)
        poster = self._render_poster(image, crop_settings or PosterCropSettings())
        return self._save_image(poster, destination_dir / POSTER_FILENAME, source_url=image_url)

    def process_local_poster(
        self,
        poster_path: Path,
        crop_settings: PosterCropSettings | None = None,
    ) -> ArtworkResult:
        """Resize and overwrite an existing local poster file."""
        image = self._open_local_image(poster_path)
        poster = self._render_poster(image, crop_settings or PosterCropSettings())
        return self._save_image(poster, poster_path, source_url=str(poster_path))

    def process_background(self, image_url: str, destination_dir: Path) -> ArtworkResult:
        """Download and save a background image with a recommended 16:9 fit."""
        image = self._download_image(image_url)
        background = ImageOps.fit(image.convert("RGB"), self._background_canvas_size(image), method=Image.Resampling.LANCZOS)
        return self._save_image(background, destination_dir / BACKGROUND_FILENAME, source_url=image_url)

    def validate_poster_recommendation(self, image_url: str) -> str:
        """Return a recommendation message for poster sizing."""
        image = self._download_image(image_url)
        if image.width >= POSTER_MIN_WIDTH and image.height >= POSTER_MIN_HEIGHT:
            return "Poster dimensions meet the 600x900 recommendation."
        return "Poster is below the recommended 600x900 size and may distort."

    def build_poster_preview_bytes(
        self,
        image_url: str,
        crop_settings: PosterCropSettings | None = None,
    ) -> bytes:
        """Render a poster preview from a remote image and return JPEG bytes."""
        image = self._download_image(image_url)
        poster = self._render_poster(image, crop_settings or PosterCropSettings())
        return self._to_jpeg_bytes(poster)

    def build_local_poster_preview_bytes(
        self,
        poster_path: Path,
        crop_settings: PosterCropSettings | None = None,
    ) -> bytes:
        """Render a poster preview from an existing local poster file."""
        image = self._open_local_image(poster_path)
        poster = self._render_poster(image, crop_settings or PosterCropSettings())
        return self._to_jpeg_bytes(poster)

    def fetch_source_bytes(self, image_url: str) -> tuple[bytes, str]:
        """Return original remote image bytes and a browser-safe content type."""
        extension = FileNameUtils.extension(image_url)
        self._validate_extension(extension)
        return self._http_client.get_bytes(image_url), self._content_type(extension)

    def fetch_local_source_bytes(self, poster_path: Path) -> tuple[bytes, str]:
        """Return original local image bytes and a browser-safe content type."""
        extension = poster_path.suffix.lower()
        self._validate_extension(extension)
        return poster_path.read_bytes(), self._content_type(extension)

    def _download_image(self, image_url: str) -> Image.Image:
        """Download an allowed image and decode it with Pillow."""
        extension = FileNameUtils.extension(image_url)
        self._validate_extension(extension)
        image_bytes = self._http_client.get_bytes(image_url)
        return Image.open(BytesIO(image_bytes))

    def _open_local_image(self, poster_path: Path) -> Image.Image:
        """Open an allowed local image with Pillow."""
        self._validate_extension(poster_path.suffix.lower())
        return Image.open(poster_path)

    def _validate_extension(self, extension: str) -> None:
        """Validate supported image extensions."""
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError("Image must use png, jpg, or jpeg.")

    def _render_poster(self, image: Image.Image, crop_settings: PosterCropSettings) -> Image.Image:
        """Render a poster using cover or contain behavior plus pan and zoom."""
        base_image = ImageOps.exif_transpose(image).convert("RGB")
        canvas_size = self._poster_canvas_size(base_image)
        if crop_settings.mode == "contain":
            return self._render_contain(base_image, canvas_size, crop_settings)
        return self._render_cover(base_image, canvas_size, crop_settings)

    def _poster_canvas_size(self, image: Image.Image) -> tuple[int, int]:
        """Pick a poster output size while honoring the 2:3 ratio."""
        width = max(POSTER_MIN_WIDTH, min(image.width, 2000))
        height = int(width * POSTER_RATIO[1] / POSTER_RATIO[0])
        return width, height

    def _background_canvas_size(self, image: Image.Image) -> tuple[int, int]:
        """Pick a background output size using the 16:9 ratio."""
        width = max(1280, min(image.width, 3840))
        height = int(width * BACKGROUND_RATIO[1] / BACKGROUND_RATIO[0])
        return width, height

    def _render_cover(
        self,
        image: Image.Image,
        canvas_size: tuple[int, int],
        crop_settings: PosterCropSettings,
    ) -> Image.Image:
        """Fill the poster frame while allowing pan and zoom."""
        canvas_width, canvas_height = canvas_size
        base_scale = max(canvas_width / image.width, canvas_height / image.height)
        scale = max(base_scale * max(crop_settings.zoom, 1.0), 0.01)
        resized = self._resize_image(image, scale)
        return self._paste_centered(resized, canvas_size, crop_settings, fill=(0, 0, 0))

    def _render_contain(
        self,
        image: Image.Image,
        canvas_size: tuple[int, int],
        crop_settings: PosterCropSettings,
    ) -> Image.Image:
        """Fit the full image inside the poster frame and allow black padding."""
        canvas_width, canvas_height = canvas_size
        base_scale = min(canvas_width / image.width, canvas_height / image.height)
        scale = max(base_scale * max(crop_settings.zoom, 0.2), 0.01)
        resized = self._resize_image(image, scale)
        return self._paste_centered(resized, canvas_size, crop_settings, fill=(0, 0, 0))

    def _resize_image(self, image: Image.Image, scale: float) -> Image.Image:
        """Resize an image using high-quality resampling."""
        width = max(1, int(image.width * scale))
        height = max(1, int(image.height * scale))
        return image.resize((width, height), Image.Resampling.LANCZOS)

    def _paste_centered(
        self,
        image: Image.Image,
        canvas_size: tuple[int, int],
        crop_settings: PosterCropSettings,
        fill: tuple[int, int, int],
    ) -> Image.Image:
        """Paste a resized image onto a canvas using normalized offsets."""
        canvas_width, canvas_height = canvas_size
        canvas = Image.new("RGB", canvas_size, fill)
        x_space = canvas_width - image.width
        y_space = canvas_height - image.height
        x_pos = int(x_space * self._normalize_offset(crop_settings.offset_x))
        y_pos = int(y_space * self._normalize_offset(crop_settings.offset_y))
        canvas.paste(image, (x_pos, y_pos))
        return canvas

    def _normalize_offset(self, offset: float) -> float:
        """Clamp offsets into a normalized 0..1 range."""
        return max(0.0, min(float(offset), 1.0))

    def _to_jpeg_bytes(self, image: Image.Image) -> bytes:
        """Serialize an image to JPEG bytes."""
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=95)
        return buffer.getvalue()

    def _content_type(self, extension: str) -> str:
        """Map an extension to a browser content type."""
        if extension == ".png":
            return "image/png"
        return "image/jpeg"

    def _save_image(self, image: Image.Image, target: Path, source_url: str) -> ArtworkResult:
        """Save an image while preserving png or jpeg output when possible."""
        self._filesystem_service.ensure_directory(target.parent)
        image_format = "PNG" if target.suffix.lower() == ".png" else "JPEG"
        save_kwargs = {"format": image_format}
        if image_format == "JPEG":
            save_kwargs["quality"] = 95
        image.save(target, **save_kwargs)
        self._filesystem_service.normalize_file(target)
        return ArtworkResult(source_url=source_url, saved_path=target, width=image.width, height=image.height)
