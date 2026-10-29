"""
Тесты fallback провайдеров (S12-002).

Основной провайдер падает → отвечает резервный; оба падают → 503 с
понятным сообщением, а не 500 и не пустой ответ.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import AsyncClient

from app.api.v1.chat import get_llm_provider
from app.main import app
from app.services.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMUnavailableError,
    LLMUsage,
)
from app.services.llm.fallback import UNAVAILABLE_DETAIL, FallbackProvider
from app.services.llm.metrics import llm_metrics

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


class FakeProvider(LLMProvider):
    """Провайдер с управляемым поведением"""

    def __init__(
        self,
        name: str,
        *,
        fail: bool = False,
        reply: str = "ответ",
        deltas: list[str] | None = None,
        fail_after: int | None = None,
        usage: LLMUsage | None = None,
    ) -> None:
        self.name = name
        self.model = f"{name}-model"
        self.fail = fail
        self.reply = reply
        self.deltas = deltas or ["от", "вет"]
        self.fail_after = fail_after
        self.usage = usage
        self.calls = 0

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        self.calls += 1
        if self.fail:
            raise LLMUnavailableError(f"{self.name} недоступен")
        self.last_usage = self.usage
        return self.reply

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        self.calls += 1
        if self.fail:
            raise LLMUnavailableError(f"{self.name} недоступен")
        for index, delta in enumerate(self.deltas):
            if self.fail_after is not None and index == self.fail_after:
                raise LLMUnavailableError(f"{self.name} оборвался")
            self.last_usage = self.usage
            yield delta


@pytest.fixture(autouse=True)
def clear_metrics() -> None:
    llm_metrics.reset()


async def _collect(provider: LLMProvider) -> str:
    chunks: list[str] = []
    async for delta in provider.stream(
        [LLMMessage(role="user", content="вопрос")]
    ):
        chunks.append(delta)
    return "".join(chunks)


async def test_generate_uses_fallback_when_primary_fails() -> None:
    primary = FakeProvider("primary", fail=True)
    fallback = FakeProvider("backup", reply="ответ резерва", usage=None)
    provider = FallbackProvider(primary, fallback)

    result = await provider.generate([LLMMessage(role="user", content="вопрос")])

    assert result == "ответ резерва"
    assert primary.calls == 1
    assert fallback.calls == 1
    assert provider.used_provider == "backup"
    assert llm_metrics.snapshot()["fallback_used"] == 1


async def test_both_providers_fail_returns_readable_error() -> None:
    provider = FallbackProvider(
        FakeProvider("primary", fail=True), FakeProvider("backup", fail=True)
    )

    with pytest.raises(LLMUnavailableError) as exc_info:
        await provider.generate([LLMMessage(role="user", content="вопрос")])

    assert str(exc_info.value) == UNAVAILABLE_DETAIL
    assert "резервный" in str(exc_info.value)


async def test_stream_falls_back_before_first_token() -> None:
    primary = FakeProvider("primary", fail=True)
    fallback = FakeProvider("backup", deltas=["резерв", "ный"])
    provider = FallbackProvider(primary, fallback)

    answer = await _collect(provider)

    assert answer == "резервный"
    assert provider.used_provider == "backup"
    assert fallback.calls == 1


async def test_stream_does_not_fallback_after_first_token() -> None:
    """Часть ответа уже показана ученику — переключение невозможно"""
    primary = FakeProvider("primary", deltas=["начало", "конец"], fail_after=1)
    fallback = FakeProvider("backup")
    provider = FallbackProvider(primary, fallback)

    chunks: list[str] = []
    with pytest.raises(LLMUnavailableError):
        async for delta in provider.stream(
            [LLMMessage(role="user", content="вопрос")]
        ):
            chunks.append(delta)

    assert chunks == ["начало"]
    assert fallback.calls == 0


async def test_stream_primary_success_keeps_primary() -> None:
    primary = FakeProvider("primary", deltas=["a", "b"])
    fallback = FakeProvider("backup")
    provider = FallbackProvider(primary, fallback)

    assert await _collect(provider) == "ab"
    assert provider.used_provider == "primary"
    assert fallback.calls == 0


async def test_last_usage_taken_from_used_provider() -> None:
    usage = LLMUsage(prompt_tokens=10, completion_tokens=5)
    primary = FakeProvider("primary", fail=True)
    fallback = FakeProvider("backup", usage=usage)
    provider = FallbackProvider(primary, fallback)

    await provider.generate([LLMMessage(role="user", content="вопрос")])

    assert provider.last_usage == usage


async def test_chat_api_returns_503_when_both_providers_fail(
    client: AsyncClient,
) -> None:
    """Интеграция: ошибка провайдеров → 503, а не 500"""
    provider = FallbackProvider(
        FakeProvider("primary", fail=True), FakeProvider("backup", fail=True)
    )
    app.dependency_overrides[get_llm_provider] = lambda: provider
    try:
        await client.post(
            REGISTER_URL,
            json={
                "email": "llmdown@example.com",
                "username": "llmdown",
                "password": "password123",
            },
        )
        token = (
            await client.post(
                LOGIN_URL, data={"username": "llmdown", "password": "password123"}
            )
        ).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        session = (
            await client.post("/api/v1/chat/sessions", json={}, headers=headers)
        ).json()

        response = await client.post(
            f"/api/v1/chat/sessions/{session['id']}/messages",
            json={"content": "Почему не работает цикл?"},
            headers=headers,
        )
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)

    assert response.status_code == 503
    detail: Any = response.json()["detail"]
    assert "недоступен" in detail
