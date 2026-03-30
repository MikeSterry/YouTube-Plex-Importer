"""Repository for output directory operations."""

from pathlib import Path
from typing import Iterable, List
from urllib.parse import unquote

from app.models.domain import UpdateTarget
from app.models.responses import OutputEntry
from app.utils.constants import ALLOWED_IMAGE_EXTENSIONS, VIDEO_EXTENSIONS


class OutputRepository:
    """Encapsulates output directory discovery and persistence details."""

    def __init__(self, settings, filesystem_service) -> None:
        """Store dependencies and ensure base directories exist."""
        self._settings = settings
        self._filesystem_service = filesystem_service
        self._filesystem_service.ensure_directory(Path(settings.output_dir))
        self._filesystem_service.ensure_directory(Path(settings.inprogress_dir))

    def create_work_dir(self, output_name: str) -> Path:
        """Create and return a working directory for a new request."""
        path = Path(self._settings.inprogress_dir) / output_name
        self._filesystem_service.ensure_directory(path)
        return path

    def create_output_dir(self, output_name: str) -> Path:
        """Create and return a final output directory."""
        path = Path(self._settings.output_dir) / output_name
        self._filesystem_service.ensure_directory(path)
        return path

    def list_outputs(self) -> List[OutputEntry]:
        """List output folders using relative paths so nested folders remain selectable."""
        base = Path(self._settings.output_dir).resolve()
        entries = []
        for directory in self._iter_output_directories(base):
            relative_path = directory.relative_to(base).as_posix()
            files = sorted([child.name for child in directory.iterdir() if child.is_file()])
            entries.append(OutputEntry(name=relative_path, path=relative_path, files=files))
        return entries

    def list_poster_files(self, output_name: str) -> list[str]:
        """Return editable local image files for one output folder."""
        directory = self._resolve_output_dir(output_name)
        files = [item.name for item in sorted(directory.iterdir()) if self._is_editable_image(item)]
        return files

    def find_update_target(self, output_name: str) -> UpdateTarget:
        """Resolve an existing output folder and its primary MKV file."""
        directory = self._resolve_output_dir(output_name)
        mkv_path = self._find_primary_mkv(directory)
        return UpdateTarget(output_name=output_name, mkv_path=mkv_path, directory=directory)

    def resolve_poster_file(self, output_name: str, file_name: str) -> Path:
        """Resolve a local poster file inside an output folder safely."""
        directory = self._resolve_output_dir(output_name)
        target = (directory / file_name).resolve()
        if directory.resolve() not in target.parents or not target.is_file():
            raise FileNotFoundError(f"Poster file not found: {file_name}")
        if target.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError("Poster file must be png, jpg, or jpeg.")
        return target

    def _resolve_output_dir(self, output_name: str) -> Path:
        """Resolve an existing output directory from exact, relative, or normalized names."""
        base = Path(self._settings.output_dir).resolve()
        requested_name = self._normalize_lookup_value(output_name)
        direct_match = self._safe_join(base, requested_name)
        if direct_match and direct_match.is_dir():
            return direct_match
        fallback_match = self._find_directory_match(base, requested_name)
        if fallback_match:
            return fallback_match
        raise FileNotFoundError(f"Output directory not found: {output_name}")

    def _iter_output_directories(self, base: Path) -> Iterable[Path]:
        """Yield selectable output directories beneath the output root."""
        directories = [item for item in base.rglob('*') if item.is_dir()]
        return sorted(directories, key=lambda value: str(value.relative_to(base)).lower())

    def _find_directory_match(self, base: Path, requested_name: str) -> Path | None:
        """Search for a directory by normalized relative path or leaf directory name."""
        normalized_request = self._normalize_compare_value(requested_name)
        matches = []
        for directory in self._iter_output_directories(base):
            relative_path = directory.relative_to(base).as_posix()
            if self._normalize_compare_value(relative_path) == normalized_request:
                matches.append(directory.resolve())
                continue
            if self._normalize_compare_value(directory.name) == normalized_request:
                matches.append(directory.resolve())
        return matches[0] if len(matches) == 1 else None

    def _safe_join(self, base: Path, relative_name: str) -> Path | None:
        """Resolve a child path safely beneath the output root."""
        candidate = (base / relative_name).resolve()
        if candidate == base or base not in candidate.parents:
            return None
        return candidate

    def _normalize_lookup_value(self, value: str) -> str:
        """Normalize submitted folder names before filesystem lookups."""
        return unquote((value or '').strip()).replace('\\', '/').strip('/')

    def _normalize_compare_value(self, value: str) -> str:
        """Normalize directory names for forgiving comparisons."""
        normalized = self._normalize_lookup_value(value).casefold()
        return ' '.join(normalized.replace('_', ' ').replace('-', ' - ').split())

    def _find_primary_mkv(self, directory: Path):
        """Return the first MKV file inside the target directory."""
        for child in sorted(directory.iterdir()):
            if child.is_file() and child.suffix.lower() in VIDEO_EXTENSIONS:
                return child
        return None

    def _is_editable_image(self, path: Path) -> bool:
        """Determine whether a file is a supported editable image."""
        return path.is_file() and path.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS
