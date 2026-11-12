"""Storage abstraction. Uploads and generated reports go through a ``StorageBackend``
so an S3-compatible backend can later replace local disk without touching callers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import BinaryIO


@dataclass(frozen=True)
class StoredObject:
    key: str
    size_bytes: int
    sha256: str


class StorageBackend(ABC):
    @abstractmethod
    def save(self, key: str, stream: BinaryIO, max_bytes: int | None = None) -> StoredObject:
        """Persist ``stream`` under ``key``. Raises FileTooLargeError past ``max_bytes``."""

    @abstractmethod
    def read_bytes(self, key: str) -> bytes: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...
