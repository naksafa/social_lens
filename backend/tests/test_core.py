import io
import json
import logging
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.error_handlers import register_error_handlers
from app.core.exceptions import FileTooLargeError, InvalidDatasetError, StorageError
from app.core.logging import JsonFormatter
from app.storage.local import LocalStorage
from app.utils.files import file_extension, sanitize_filename


class TestSanitizeFilename:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("report.csv", "report.csv"),
            ("../../etc/passwd", "passwd"),
            ("..\\..\\windows\\evil.xlsx", "evil.xlsx"),
            ("Instagram Export (Sept).csv", "Instagram_Export_Sept_.csv"),
            ("données_été.xlsx", "donnees_ete.xlsx"),
            ("...", "upload"),
            ("", "upload"),
        ],
    )
    def test_sanitizes(self, raw: str, expected: str) -> None:
        assert sanitize_filename(raw) == expected

    def test_truncates_but_keeps_extension(self) -> None:
        name = sanitize_filename("a" * 300 + ".csv", max_length=50)
        assert len(name) == 50
        assert name.endswith(".csv")

    def test_extension_is_lowercased(self) -> None:
        assert file_extension("DATA.XLSX") == ".xlsx"


class TestLocalStorage:
    def test_roundtrip(self, tmp_storage_root: Path) -> None:
        storage = LocalStorage(tmp_storage_root)
        obj = storage.save("p1/file.csv", io.BytesIO(b"a,b\n1,2\n"))
        assert obj.size_bytes == 8
        assert len(obj.sha256) == 64
        assert storage.exists("p1/file.csv")
        assert storage.read_bytes("p1/file.csv") == b"a,b\n1,2\n"
        storage.delete("p1/file.csv")
        assert not storage.exists("p1/file.csv")

    def test_rejects_path_traversal(self, tmp_storage_root: Path) -> None:
        storage = LocalStorage(tmp_storage_root)
        with pytest.raises(StorageError):
            storage.save("../outside.csv", io.BytesIO(b"x"))

    def test_enforces_size_limit_and_leaves_no_partial_file(self, tmp_storage_root: Path) -> None:
        storage = LocalStorage(tmp_storage_root)
        with pytest.raises(FileTooLargeError):
            storage.save("big.csv", io.BytesIO(b"x" * 100), max_bytes=10)
        assert not storage.exists("big.csv")
        assert not any(tmp_storage_root.rglob("*.part"))


class TestSettings:
    def test_comma_separated_lists(self) -> None:
        s = Settings(cors_origins="http://a.com, http://b.com", _env_file=None)
        assert s.cors_origins == ["http://a.com", "http://b.com"]

    def test_empty_api_key_means_not_configured(self) -> None:
        s = Settings(ai_provider="anthropic", anthropic_api_key="", _env_file=None)
        assert s.anthropic_api_key is None
        assert not s.ai_configured

    def test_secret_not_leaked_in_repr(self) -> None:
        s = Settings(ai_provider="anthropic", anthropic_api_key="sk-ant-supersecretvalue", _env_file=None)
        assert "supersecret" not in repr(s)
        assert s.ai_configured


class TestLoggingRedaction:
    def _format(self, msg: str, **extra: object) -> dict:
        record = logging.LogRecord("t", logging.INFO, __file__, 1, msg, (), None)
        for k, v in extra.items():
            setattr(record, k, v)
        return json.loads(JsonFormatter().format(record))

    def test_sensitive_fields_redacted(self) -> None:
        out = self._format("ai.request", api_key="sk-live-123456789", provider="anthropic")
        assert out["api_key"] == "***"
        assert out["provider"] == "anthropic"

    def test_inline_keys_masked(self) -> None:
        out = self._format("using key sk-ant-abcdefghijklmnop now")
        assert "abcdefgh" not in out["event"]


class TestErrorShape:
    def test_app_errors_render_structured_json(self) -> None:
        app = FastAPI()
        register_error_handlers(app)

        @app.get("/boom")
        def boom() -> None:
            raise InvalidDatasetError("Dataset is empty.", {"rows": 0})

        @app.get("/crash")
        def crash() -> None:
            raise RuntimeError("secret internals")

        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/boom")
        assert r.status_code == 422
        assert r.json() == {
            "code": "invalid_dataset",
            "message": "Dataset is empty.",
            "details": {"rows": 0},
        }
        r = client.get("/crash")
        assert r.status_code == 500
        assert r.json()["code"] == "internal_error"
        assert "secret internals" not in r.text
