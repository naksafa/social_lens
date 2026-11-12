from functools import lru_cache

from app.core.config import get_settings
from app.storage.base import StorageBackend, StoredObject
from app.storage.local import LocalStorage

__all__ = ["StorageBackend", "StoredObject", "get_storage"]


@lru_cache
def get_storage() -> StorageBackend:
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalStorage(settings.storage_local_path)
    raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")
