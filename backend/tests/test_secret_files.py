"""Секреты из файлов `*_FILE` (S38-002)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings


def _secret(tmp_path: Path, name: str, value: str) -> Path:
    path = tmp_path / name
    path.write_text(value, encoding="utf-8")
    return path


def test_secret_key_file_overrides_env(tmp_path: Path) -> None:
    """Файл приоритетнее ENV; перевод строки в конце отбрасывается."""
    path = _secret(tmp_path, "secret_key", "file-secret-" + "x" * 32 + "\n")

    settings = Settings(
        _env_file=None,
        secret_key="env-secret",
        secret_key_file=str(path),
    )

    assert settings.secret_key == "file-secret-" + "x" * 32


def test_postgres_password_file(tmp_path: Path) -> None:
    path = _secret(tmp_path, "pg_password", "db-from-file\n")

    settings = Settings(
        _env_file=None,
        postgres_password="env-password",
        postgres_password_file=str(path),
    )

    assert settings.postgres_password == "db-from-file"
    assert "db-from-file" in settings.database_url


def test_deepseek_and_sentry_files(tmp_path: Path) -> None:
    api_key = _secret(tmp_path, "deepseek", "sk-file")
    dsn = _secret(tmp_path, "sentry", "https://key@example.ingest.sentry.io/1\n")

    settings = Settings(
        _env_file=None,
        deepseek_api_key="env-key",
        deepseek_api_key_file=str(api_key),
        sentry_dsn="",
        sentry_dsn_file=str(dsn),
    )

    assert settings.deepseek_api_key == "sk-file"
    assert settings.sentry_dsn == "https://key@example.ingest.sentry.io/1"


def test_missing_secret_file_fails_fast(tmp_path: Path) -> None:
    """Не читаемый файл — ошибка конфигурации, а не пустой секрет."""
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            secret_key_file=str(tmp_path / "missing"),
        )


def test_empty_secret_file_fails_fast(tmp_path: Path) -> None:
    path = _secret(tmp_path, "empty", "")

    with pytest.raises(ValidationError):
        Settings(_env_file=None, secret_key_file=str(path))


def test_no_file_keeps_env_value() -> None:
    settings = Settings(_env_file=None, postgres_password="env-password")

    assert settings.postgres_password == "env-password"
