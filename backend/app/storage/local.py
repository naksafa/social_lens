import hashlib
from pathlib import Path
from typing import BinaryIO

from app.core.exceptions import FileTooLargeError, NotFoundError, StorageError
from app.storage.base import StorageBackend, StoredObject

_CHUNK = 1024 * 1024


class LocalStorage(StorageBackend):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        # Guard against path traversal via crafted keys ("../../etc/passwd").
        if not path.is_relative_to(self.root):
            raise StorageError("Invalid storage key.", {"key": key})
        return path

    def save(self, key: str, stream: BinaryIO, max_bytes: int | None = None) -> StoredObject:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size = 0
        tmp = path.with_suffix(path.suffix + ".part")
        try:
            with tmp.open("wb") as out:
                while chunk := stream.read(_CHUNK):
                    size += len(chunk)
                    if max_bytes is not None and size > max_bytes:
                        raise FileTooLargeError(
                            "File exceeds the maximum upload size.",
                            {"max_bytes": max_bytes},
                        )
                    digest.update(chunk)
                    out.write(chunk)
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)
        return StoredObject(key=key, size_bytes=size, sha256=digest.hexdigest())

    def read_bytes(self, key: str) -> bytes:
        path = self._path(key)
        if not path.is_file():
            raise NotFoundError("Stored file not found.", {"key": key})
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
