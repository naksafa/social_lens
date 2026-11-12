"""Test configuration.

Tests run against an isolated SQLite database and a temp storage dir so they
need neither Docker nor PostgreSQL. Env vars must be set before ``app`` is
imported because settings and the engine are created at import time.
"""

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="sociallens-test-"))
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["STORAGE_LOCAL_PATH"] = str(_TMP / "storage")
os.environ["LOG_JSON"] = "false"
os.environ["AI_PROVIDER"] = "none"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_schema() -> Iterator[None]:
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def tmp_storage_root(tmp_path: Path) -> Path:
    return tmp_path / "store"
