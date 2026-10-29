"""
Тесты rate limiting (S11-003, закрывает KI-007).

Используется in-memory фейк Redis: тесты не зависят от внешнего сервиса и
не мешают другим прогонам. Проверяется и сам счётчик, и middleware целиком.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.core.rate_limiter import (
    LOGIN_LIMIT,
    LOGIN_PATH,
    RateLimiter,
    RateLimitMiddleware,
)

LOGIN_DATA = {"username": "nobody", "password": "wrong-password"}


class FakeRedis:
    """Минимальная реализация нужных команд Redis"""

    def __init__(self) -> None:
        self.data: dict[str, int] = {}

    async def get(self, key: str) -> int | None:
        return self.data.get(key)

    async def setex(self, key: str, ttl: int, value: int) -> None:
        self.data[key] = value

    async def incr(self, key: str) -> None:
        self.data[key] = self.data.get(key, 0) + 1


class BrokenRedis:
    """Клиент, который всегда падает (имитация недоступного Redis)"""

    async def get(self, key: str) -> None:
        raise ConnectionError("redis is down")

    async def setex(self, key: str, ttl: int, value: int) -> None:
        raise ConnectionError("redis is down")

    async def incr(self, key: str) -> None:
        raise ConnectionError("redis is down")


def _probe_app(redis_factory: Any) -> FastAPI:
    """Мини-приложение с middleware лимитов"""
    probe = FastAPI()
    probe.add_middleware(RateLimitMiddleware, redis_factory=redis_factory)

    @probe.get("/api/v1/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    @probe.post(LOGIN_PATH)
    async def login() -> dict[str, bool]:
        return {"ok": True}

    @probe.get("/api/v1/other")
    async def other() -> dict[str, bool]:
        return {"ok": True}

    return probe


@pytest.fixture
async def probe_client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[AsyncClient]:
    """Клиент мини-приложения с включёнными лимитами и чистым фейком"""
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    redis = FakeRedis()
    app = _probe_app(lambda: redis)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# --- Счётчик ------------------------------------------------------------


async def test_counter_blocks_after_limit() -> None:
    """RateLimiter пропускает ровно limit запросов"""
    limiter = RateLimiter(FakeRedis())  # type: ignore[arg-type]

    results = [await limiter.is_limited("k", limit=3) for _ in range(5)]

    assert results == [False, False, False, True, True]


async def test_remaining_decreases() -> None:
    """get_remaining считает остаток"""
    redis = FakeRedis()
    limiter = RateLimiter(redis)  # type: ignore[arg-type]

    await limiter.is_limited("k", limit=5)
    await limiter.is_limited("k", limit=5)

    assert await limiter.get_remaining("k", limit=5) == 3
    assert await limiter.get_remaining("unknown", limit=5) == 5


# --- Middleware ---------------------------------------------------------


async def test_login_returns_429_after_limit(probe_client: AsyncClient) -> None:
    """После LOGIN_LIMIT входов возвращается 429"""
    statuses = [
        (await probe_client.post(LOGIN_PATH, data=LOGIN_DATA)).status_code
        for _ in range(LOGIN_LIMIT + 1)
    ]

    assert statuses[:LOGIN_LIMIT] == [200] * LOGIN_LIMIT
    assert statuses[LOGIN_LIMIT] == 429


async def test_429_has_retry_after_header(probe_client: AsyncClient) -> None:
    """Ответ 429 содержит Retry-After"""
    for _ in range(LOGIN_LIMIT):
        await probe_client.post(LOGIN_PATH, data=LOGIN_DATA)

    response = await probe_client.post(LOGIN_PATH, data=LOGIN_DATA)

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    assert "Слишком много запросов" in response.json()["detail"]


async def test_health_is_exempt(probe_client: AsyncClient) -> None:
    """Health-check не лимитируется"""
    for _ in range(LOGIN_LIMIT + 10):
        response = await probe_client.get("/api/v1/health")

    assert response.status_code == 200


async def test_general_limit_is_higher(probe_client: AsyncClient) -> None:
    """Обычные запросы не блокируются на login-лимите"""
    for _ in range(LOGIN_LIMIT + 5):
        response = await probe_client.get("/api/v1/other")

    assert response.status_code == 200


async def test_limits_disabled_by_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """При RATE_LIMIT_ENABLED=false middleware ничего не считает"""
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    redis = FakeRedis()
    app = _probe_app(lambda: redis)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(LOGIN_LIMIT + 3):
            response = await client.post(LOGIN_PATH, data=LOGIN_DATA)

    assert response.status_code == 200
    assert redis.data == {}


async def test_fail_open_when_redis_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redis недоступен → запросы проходят, API не падает"""
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    app = _probe_app(lambda: BrokenRedis())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(LOGIN_PATH, data=LOGIN_DATA)

    assert response.status_code == 200


async def test_fail_open_when_factory_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Фабрика клиента бросает исключение → запрос всё равно проходит"""
    monkeypatch.setattr(settings, "rate_limit_enabled", True)

    def failing_factory() -> Any:
        raise RuntimeError("no redis configured")

    app = _probe_app(failing_factory)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/other")

    assert response.status_code == 200


async def test_forwarded_for_is_used_as_key() -> None:
    """Ключом служит первый адрес из X-Forwarded-For"""
    middleware = RateLimitMiddleware.__new__(RateLimitMiddleware)

    class RequestStub:
        headers = {"x-forwarded-for": "203.0.113.5, 10.0.0.1"}
        client = None
        url = type("Url", (), {"path": "/api/v1/other"})()

    assert middleware._client_ip(RequestStub()) == "203.0.113.5"  # type: ignore[arg-type]
