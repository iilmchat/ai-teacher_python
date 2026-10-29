"""
Тесты healthcheck LLM-провайдера (S12-001).

Проверяем кэш, статусы `ok` / `degraded` / `not_configured` и то, что
ключ никогда не попадает в ответ `/health`.
"""

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services.llm.base import LLMMessage, LLMProvider
from app.services.llm.health import (
    CACHE_TTL_SECONDS,
    check_provider_health,
    reset_health_cache,
)


class HealthProvider(LLMProvider):
    """Провайдер с управляемыми `is_configured` и `ping`"""

    name = "fake"
    model = "fake-model"

    def __init__(self, configured: bool = True, reachable: bool = True) -> None:
        self.configured = configured
        self.reachable = reachable
        self.pings = 0

    def is_configured(self) -> bool:
        return self.configured

    async def ping(self) -> bool:
        self.pings += 1
        return self.reachable

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        return "ok"

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        yield "ok"


@pytest.fixture(autouse=True)
def clear_health_cache() -> None:
    reset_health_cache()


async def test_configured_and_reachable_is_ok() -> None:
    provider = HealthProvider()

    health = await check_provider_health(provider)

    assert health.status == "ok"
    assert health.configured is True
    assert health.reachable is True


async def test_configured_but_unreachable_is_degraded() -> None:
    provider = HealthProvider(reachable=False)

    health = await check_provider_health(provider)

    assert health.status == "degraded"
    assert health.reachable is False


async def test_not_configured_never_pings() -> None:
    provider = HealthProvider(configured=False)

    health = await check_provider_health(provider)

    assert health.status == "not_configured"
    assert health.reachable is False
    assert provider.pings == 0


async def test_result_is_cached_for_ttl() -> None:
    provider = HealthProvider()

    await check_provider_health(provider, now=100.0)
    await check_provider_health(provider, now=100.0 + CACHE_TTL_SECONDS / 2)

    assert provider.pings == 1


async def test_cache_expires_after_ttl() -> None:
    provider = HealthProvider()

    await check_provider_health(provider, now=100.0)
    await check_provider_health(provider, now=100.0 + CACHE_TTL_SECONDS + 1)

    assert provider.pings == 2


async def test_health_endpoint_reports_not_configured_without_key(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Без ключа статус — not_configured, а не ok (урок из chess-проекта)"""
    monkeypatch.setattr(settings, "llm_provider", "deepseek")
    monkeypatch.setattr(settings, "llm_fallback_provider", "")
    monkeypatch.setattr(settings, "deepseek_api_key", "change_me_api_key")

    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["llm"]["status"] == "not_configured"
    assert body["llm"]["configured"] is False
    assert body["llm"]["reachable"] is False
    assert "change_me_api_key" not in response.text


async def test_health_endpoint_reports_ok_for_echo(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Детерминированный провайдер настроен и доступен"""
    monkeypatch.setattr(settings, "llm_provider", "echo")
    monkeypatch.setattr(settings, "llm_fallback_provider", "")

    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    llm = response.json()["llm"]
    assert llm["provider"] == "echo"
    assert llm["model"] == "echo"
    assert llm["status"] == "ok"
    assert llm["fallback"] is None


async def test_health_reports_fallback(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Настроенный fallback виден в health, даже если основной — echo"""
    monkeypatch.setattr(settings, "llm_provider", "echo")
    monkeypatch.setattr(settings, "llm_fallback_provider", "lm_studio")
    monkeypatch.setattr(settings, "lm_studio_url", "http://localhost:1234/v1")

    response = await client.get("/api/v1/health")

    llm = response.json()["llm"]
    assert llm["fallback"] == "lm_studio"
    # Основной провайдер — echo, поэтому статус ok, а не degraded
    assert llm["status"] == "ok"
