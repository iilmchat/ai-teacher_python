"""
Тесты метрик LLM (S12-003): запросы, ошибки, латентность, токены.
"""

from collections.abc import AsyncIterator

import pytest

from app.services.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMUnavailableError,
    LLMUsage,
)
from app.services.llm.metrics import LLMMetrics, MetricsProvider


class UsageProvider(LLMProvider):
    """Провайдер с заданным usage и управляемой ошибкой"""

    name = "usage"
    model = "usage-model"

    def __init__(
        self,
        usage: LLMUsage | None = None,
        *,
        fail: bool = False,
        deltas: list[str] | None = None,
    ) -> None:
        self.usage = usage or LLMUsage(prompt_tokens=20, completion_tokens=10)
        self.fail = fail
        self.deltas = deltas or ["ответ"]

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        if self.fail:
            raise LLMUnavailableError("сбой")
        self.last_usage = self.usage
        return "ответ"

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        if self.fail:
            raise LLMUnavailableError("сбой")
        for delta in self.deltas:
            self.last_usage = self.usage
            yield delta


@pytest.fixture
def registry() -> LLMMetrics:
    return LLMMetrics()


async def test_generate_records_tokens_and_latency(registry: LLMMetrics) -> None:
    provider = MetricsProvider(UsageProvider(), registry)

    await provider.generate([LLMMessage(role="user", content="вопрос")])

    snapshot = registry.snapshot()
    hour = snapshot["last_hour"]
    assert hour["requests"] == 1
    assert hour["errors"] == 0
    assert hour["prompt_tokens"] == 20
    assert hour["completion_tokens"] == 10
    assert hour["total_tokens"] == 30
    assert hour["avg_latency_ms"] >= 0
    assert snapshot["fallback_used"] == 0


async def test_error_is_recorded(registry: LLMMetrics) -> None:
    provider = MetricsProvider(UsageProvider(fail=True), registry)

    with pytest.raises(LLMUnavailableError):
        await provider.generate([LLMMessage(role="user", content="вопрос")])

    hour = registry.snapshot()["last_hour"]
    assert hour["requests"] == 1
    assert hour["errors"] == 1
    assert hour["total_tokens"] == 0


async def test_stream_records_first_token_and_completion(registry: LLMMetrics) -> None:
    provider = MetricsProvider(UsageProvider(deltas=["раз", "два"]), registry)

    chunks = [
        delta
        async for delta in provider.stream([LLMMessage(role="user", content="вопрос")])
    ]

    assert chunks == ["раз", "два"]
    hour = registry.snapshot()["last_hour"]
    assert hour["requests"] == 1
    assert hour["avg_first_token_ms"] >= 0
    assert hour["total_tokens"] == 30


async def test_stream_error_is_recorded(registry: LLMMetrics) -> None:
    provider = MetricsProvider(UsageProvider(fail=True), registry)

    with pytest.raises(LLMUnavailableError):
        async for _ in provider.stream([LLMMessage(role="user", content="вопрос")]):
            pass

    hour = registry.snapshot()["last_hour"]
    assert hour["errors"] == 1


async def test_by_provider_aggregation(registry: LLMMetrics) -> None:
    await MetricsProvider(UsageProvider(), registry).generate(
        [LLMMessage(role="user", content="1")]
    )
    other = UsageProvider()
    other.name = "other"
    await MetricsProvider(other, registry).generate(
        [LLMMessage(role="user", content="2")]
    )

    by_provider = registry.snapshot()["last_24h"]["by_provider"]
    assert set(by_provider) == {"usage", "other"}
    assert by_provider["usage"]["requests"] == 1
    assert by_provider["other"]["total_tokens"] == 30


async def test_snapshot_has_hour_and_day_windows(registry: LLMMetrics) -> None:
    snapshot = registry.snapshot()

    assert snapshot["last_hour"]["window_hours"] == 1
    assert snapshot["last_24h"]["window_hours"] == 24
    assert snapshot["last_hour"]["requests"] == 0
    assert snapshot["last_24h"]["p95_latency_ms"] == 0
    assert "recorded_at" in snapshot


def test_reset_clears_records(registry: LLMMetrics) -> None:
    registry.record(
        provider="usage",
        model="m",
        status="ok",
        latency_ms=12,
        usage=LLMUsage(prompt_tokens=1, completion_tokens=1),
    )
    registry.record_fallback()

    registry.reset()

    snapshot = registry.snapshot()
    assert snapshot["last_hour"]["requests"] == 0
    assert snapshot["fallback_used"] == 0
