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
    REFRESH_LIMIT,
    REFRESH_PATH,
    RateLimiter,
    RateLimitMiddleware,
    is_user_limited,
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

    async def incr(self, key: str) -> int:
        """Увеличивает значение и возвращает новое значение"""
        new_value = self.data.get(key, 0) + 1
        self.data[key] = new_value
        return new_value


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

    @probe.post(REFRESH_PATH)
    async def refresh() -> dict[str, bool]:
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


# --- S34-003: защита от подделки X-Forwarded-For ---------------------------


class _RequestStub:
    """Минимальный request-стаб для проверки client_ip."""

    def __init__(self, headers: dict[str, str], peer: str | None) -> None:
        self.headers = headers
        self.client = type("Client", (), {"host": peer})() if peer else None
        self.url = type("Url", (), {"path": "/api/v1/other"})()


def test_client_ip_without_trusted_proxies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Без TRUSTED_PROXIES заголовок X-Forwarded-For игнорируется."""
    monkeypatch.setattr(settings, "trusted_proxies", [])
    from app.core.ip_utils import client_ip

    request = _RequestStub({"x-forwarded-for": "203.0.113.5, 10.0.0.1"}, "192.0.2.1")

    assert client_ip(request) == "192.0.2.1"  # type: ignore[arg-type]


def test_client_ip_trusted_proxy_returns_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Если peer — доверенный прокси, клиент берётся из X-Forwarded-For."""
    monkeypatch.setattr(settings, "trusted_proxies", ["10.0.0.1"])
    from app.core.ip_utils import client_ip

    request = _RequestStub({"x-forwarded-for": "203.0.113.5"}, "10.0.0.1")

    assert client_ip(request) == "203.0.113.5"  # type: ignore[arg-type]


def test_client_ip_rejects_untrusted_peer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Если TCP-peer не доверенный — заголовок подделан, возвращается peer."""
    monkeypatch.setattr(settings, "trusted_proxies", ["10.0.0.1"])
    from app.core.ip_utils import client_ip

    request = _RequestStub({"x-forwarded-for": "203.0.113.5"}, "192.0.2.1")

    assert client_ip(request) == "192.0.2.1"  # type: ignore[arg-type]


def test_client_ip_skips_trusted_hops_right_to_left(monkeypatch: pytest.MonkeyPatch) -> None:
    """Доверенные хопы пропускаются справа налево, клиент — первый недоверенный."""
    monkeypatch.setattr(settings, "trusted_proxies", ["10.0.0.1", "10.0.0.2"])
    from app.core.ip_utils import client_ip

    request = _RequestStub(
        {"x-forwarded-for": "203.0.113.5, 10.0.0.1"}, "10.0.0.2"
    )

    assert client_ip(request) == "203.0.113.5"  # type: ignore[arg-type]


def test_client_ip_with_cidr_trusted_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """CIDR в TRUSTED_PROXIES работает и для peer, и для хопов."""
    monkeypatch.setattr(settings, "trusted_proxies", ["10.0.0.0/8"])
    from app.core.ip_utils import client_ip

    request = _RequestStub({"x-forwarded-for": "203.0.113.5"}, "10.0.0.1")

    assert client_ip(request) == "203.0.113.5"  # type: ignore[arg-type]


def test_client_ip_no_forwarded_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """Без заголовка X-Forwarded-For возвращается TCP-peer."""
    monkeypatch.setattr(settings, "trusted_proxies", ["10.0.0.1"])
    from app.core.ip_utils import client_ip

    request = _RequestStub({}, "192.0.2.1")

    assert client_ip(request) == "192.0.2.1"  # type: ignore[arg-type]


async def test_xff_attack_does_not_bypass_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Без TRUSTED_PROXIES подмена X-Forwarded-For не обходит лимит."""
    monkeypatch.setattr(settings, "trusted_proxies", [])
    monkeypatch.setattr(settings, "rate_limit_enabled", True)

    redis = FakeRedis()
    app = _probe_app(lambda: redis)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for i in range(LOGIN_LIMIT):
            headers = {"x-forwarded-for": f"203.0.113.{i + 1}"}
            response = await client.post(LOGIN_PATH, data=LOGIN_DATA, headers=headers)
            assert response.status_code == 200

        # Меняем «IP» — ключ всё равно строится по TCP-peer, поэтому 429.
        headers = {"x-forwarded-for": "198.51.100.7"}
        response = await client.post(LOGIN_PATH, data=LOGIN_DATA, headers=headers)
        assert response.status_code == 429


async def test_xff_spoof_behind_trusted_proxy_does_not_bypass_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Подмена левой части X-Forwarded-For за доверенным прокси не обходит лимит.

    Прокси (peer 127.0.0.1) добавляет реальный IP клиента справа; клиент может
    подделать только левую часть. Ключ лимита не должен меняться.
    """
    monkeypatch.setattr(settings, "trusted_proxies", ["127.0.0.1"])
    monkeypatch.setattr(settings, "rate_limit_enabled", True)

    redis = FakeRedis()
    app = _probe_app(lambda: redis)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for i in range(LOGIN_LIMIT):
            # Меняем подделываемую левую часть, реальный IP справа неизменен.
            headers = {"x-forwarded-for": f"1.1.1.{i + 1}, 203.0.113.5"}
            response = await client.post(LOGIN_PATH, data=LOGIN_DATA, headers=headers)
            assert response.status_code == 200

        headers = {"x-forwarded-for": "9.9.9.9, 203.0.113.5"}
        response = await client.post(LOGIN_PATH, data=LOGIN_DATA, headers=headers)
        assert response.status_code == 429


# --- S34-004: отдельный лимит refresh и per-user лимит песочницы -----------


async def test_refresh_returns_429_after_limit(probe_client: AsyncClient) -> None:
    """POST /auth/refresh лимитируется отдельно от общего лимита."""
    statuses = [
        (await probe_client.post(REFRESH_PATH)).status_code
        for _ in range(REFRESH_LIMIT + 1)
    ]

    assert statuses[:REFRESH_LIMIT] == [200] * REFRESH_LIMIT
    assert statuses[REFRESH_LIMIT] == 429


async def test_refresh_limit_independent_from_login(probe_client: AsyncClient) -> None:
    """Исчерпание login-лимита не блокирует refresh."""
    for _ in range(LOGIN_LIMIT + 1):
        await probe_client.post(LOGIN_PATH, data=LOGIN_DATA)

    response = await probe_client.post(REFRESH_PATH)

    assert response.status_code == 200


async def test_is_user_limited_blocks_after_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per-user лимит блокирует после исчерпания окна."""
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    redis = FakeRedis()
    monkeypatch.setattr("app.db.redis.get_redis", lambda: redis)

    results = [
        await is_user_limited("code_execute", "user-1", limit=3) for _ in range(4)
    ]

    assert results == [False, False, False, True]


async def test_is_user_limited_isolated_per_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Лимит одного пользователя не влияет на другого."""
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    redis = FakeRedis()
    monkeypatch.setattr("app.db.redis.get_redis", lambda: redis)

    for _ in range(3):
        await is_user_limited("code_execute", "user-1", limit=3)

    assert await is_user_limited("code_execute", "user-1", limit=3) is True
    assert await is_user_limited("code_execute", "user-2", limit=3) is False


async def test_is_user_limited_disabled_by_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """При выключенном rate-limit per-user проверка ничего не блокирует."""
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    redis = FakeRedis()
    monkeypatch.setattr("app.db.redis.get_redis", lambda: redis)

    for _ in range(10):
        assert await is_user_limited("code_execute", "user-1", limit=1) is False
    assert redis.data == {}


async def test_is_user_limited_fail_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redis недоступен — per-user лимит fail-open."""
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr("app.db.redis.get_redis", lambda: BrokenRedis())

    assert await is_user_limited("code_execute", "user-1", limit=1) is False
