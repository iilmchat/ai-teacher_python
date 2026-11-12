"""Тесты fail-fast конфигурации и флага документации (S34-005, S34-006)."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import (
    DEFAULT_SECRET_KEY,
    InsecureSettingsError,
    settings,
    validate_security_settings,
)
from app.main import docs_urls

GOOD_SECRET = "x" * 40 + "-random-production-key"


# --- S34-005: fail-fast при небезопасном SECRET_KEY ------------------------


def test_default_secret_key_rejected_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Дефолтный SECRET_KEY при DEBUG=false прерывает старт."""
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "secret_key", DEFAULT_SECRET_KEY)

    with pytest.raises(InsecureSettingsError):
        validate_security_settings()


def test_short_secret_key_rejected_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Короткий SECRET_KEY (< 32) при DEBUG=false прерывает старт."""
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "secret_key", "too-short")

    with pytest.raises(InsecureSettingsError):
        validate_security_settings()


def test_good_secret_key_accepted_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Длинный случайный SECRET_KEY проходит проверку."""
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "secret_key", GOOD_SECRET)

    validate_security_settings()  # не должно бросить


def test_debug_allows_default_secret_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """В DEBUG=true дефолтный ключ допустим (локальная разработка)."""
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "secret_key", DEFAULT_SECRET_KEY)

    validate_security_settings()  # не должно бросить


# --- S34-006: DOCS_ENABLED -------------------------------------------------


def test_docs_urls_enabled() -> None:
    """При включённой документации возвращаются стандартные URL."""
    assert docs_urls(True) == {
        "docs_url": "/api/docs",
        "redoc_url": "/api/redoc",
        "openapi_url": "/api/openapi.json",
    }


def test_docs_urls_disabled() -> None:
    """При выключенной документации все URL — None."""
    assert docs_urls(False) == {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }


async def test_docs_not_served_when_disabled() -> None:
    """При DOCS_ENABLED=false Swagger/OpenAPI отдают 404."""
    probe = FastAPI(**docs_urls(False))

    @probe.get("/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    transport = ASGITransport(app=probe)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for path in ("/api/docs", "/api/redoc", "/api/openapi.json", "/openapi.json"):
            response = await client.get(path)
            assert response.status_code == 404, path


async def test_docs_served_when_enabled() -> None:
    """При DOCS_ENABLED=true Swagger и OpenAPI доступны."""
    probe = FastAPI(**docs_urls(True))

    @probe.get("/ping")
    async def ping() -> dict[str, bool]:
        return {"ok": True}

    transport = ASGITransport(app=probe)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        docs = await client.get("/api/docs")
        schema = await client.get("/api/openapi.json")

    assert docs.status_code == 200
    assert schema.status_code == 200
    assert schema.json()["info"]["title"]
