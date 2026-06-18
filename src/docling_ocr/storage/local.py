from __future__ import annotations

import logging
from pathlib import Path

from docling_ocr.exceptions import StorageError
from docling_ocr.storage.base import StorageBackend

logger = logging.getLogger(__name__)


class LocalStorageBackend(StorageBackend):
    def __init__(self, output_dir: str = "./output", subfolder: str | None = None) -> None:
        self._base_dir = Path(output_dir)
        self._subfolder = subfolder
        try:
            self.effective_output_dir.mkdir(parents=True, exist_ok=True)
            logger.info("LocalStorageBackend initialized (output_dir=%s)", self.effective_output_dir.resolve())
        except OSError as e:
            raise StorageError(f"Failed to create output directory {self.effective_output_dir}: {e}") from e

    @property
    def effective_output_dir(self) -> Path:
        if self._subfolder:
            return self._base_dir / self._subfolder
        return self._base_dir

    @property
    def _output_dir(self) -> Path:
        return self.effective_output_dir

    @_output_dir.setter
    def _output_dir(self, value: Path) -> None:
        self._base_dir = value
        self._subfolder = None

    def upload(self, file_data: bytes, filename: str, content_type: str = "image/png") -> str:
        target_dir = self.effective_output_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / filename
        logger.debug("Saving file locally: %s (%d bytes)", file_path, len(file_data))
        try:
            file_path.write_bytes(file_data)
        except OSError as e:
            raise StorageError(f"Failed to save file locally at {file_path}: {e}") from e

        resolved = str(file_path.resolve())
        logger.info("File saved: %s", resolved)
        return resolved

    def get_base_url(self) -> str:
        return str(self.effective_output_dir.resolve())
