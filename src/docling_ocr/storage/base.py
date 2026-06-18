from __future__ import annotations

from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    def upload(self, file_data: bytes, filename: str, content_type: str = "image/png") -> str:
        raise NotImplementedError

    @abstractmethod
    def get_base_url(self) -> str:
        raise NotImplementedError
