"""Filesystem and permission helpers."""

import os
from pathlib import Path
import shutil


class FilesystemService:
    """Manage directory creation, permissions, ownership, and file moves."""

    def __init__(self, settings) -> None:
        """Store ownership and mode settings."""
        self._settings = settings

    def ensure_directory(self, path: Path) -> Path:
        """Create a directory and immediately normalize its metadata."""
        path.mkdir(parents=True, exist_ok=True)
        self._apply_mode(path, self._settings.app_dir_mode)
        self._apply_owner(path)
        return path

    def normalize_file(self, path: Path) -> Path:
        """Normalize file ownership and mode after creation."""
        self._apply_mode(path, self._settings.app_file_mode)
        self._apply_owner(path)
        return path

    def write_text(self, path: Path, content: str) -> Path:
        """Write text content and normalize resulting file metadata."""
        path.write_text(content, encoding="utf-8")
        return self.normalize_file(path)

    def move_to_directory(self, source: Path, destination_dir: Path) -> Path:
        """Move a file into a destination directory and normalize metadata."""
        self.ensure_directory(destination_dir)
        target = destination_dir / source.name
        shutil.move(str(source), str(target))
        return self.normalize_file(target)

    def copy_to_directory(self, source: Path, destination_dir: Path, target_name: str | None = None) -> Path:
        """Copy a file into a destination directory and normalize metadata."""
        self.ensure_directory(destination_dir)
        target = destination_dir / (target_name or source.name)
        shutil.copy2(str(source), str(target))
        return self.normalize_file(target)

    def remove_directory(self, path: Path) -> None:
        """Delete a directory tree when it exists."""
        if path.exists():
            shutil.rmtree(path)

    def _apply_mode(self, path: Path, mode: int) -> None:
        """Apply unix permissions when supported by the current filesystem."""
        try:
            os.chmod(path, mode)
        except PermissionError:
            pass

    def _apply_owner(self, path: Path) -> None:
        """Apply ownership when supported by the current filesystem."""
        try:
            os.chown(path, self._settings.app_user_id, self._settings.app_group_id)
        except PermissionError:
            pass
        except AttributeError:
            pass
