"""
Метрики LLM-вызовов (S12-003).

Хранятся в памяти процесса: запросы, ошибки, fallback, латентность,
токены — агрегаты за час и сутки. Содержимое промптов и ответов не
сохраняется (RULES §8.4): только метаданные вызова.
"""

import math
import time
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any

from app.services.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMUnavailableError,
    LLMUsage,
)

#: Сколько последних вызовов держим в памяти (защита от роста)
MAX_RECORDS = 1000


@dataclass(frozen=True, slots=True)
class LLMCall:
    """Один вызов провайдера"""

    provider: str
    model: str
    status: str  # ok | error
    latency_ms: int
    first_token_ms: int | None
    prompt_tokens: int
    completion_tokens: int
    created_at: datetime


class LLMMetrics:
    """Потокобезопасный реестр вызовов LLM"""

    def __init__(self, max_records: int = MAX_RECORDS) -> None:
        self._records: deque[LLMCall] = deque(maxlen=max_records)
        self._fallbacks = 0
        self._lock = Lock()

    def record(
        self,
        *,
        provider: str,
        model: str,
        status: str,
        latency_ms: int,
        first_token_ms: int | None = None,
        usage: LLMUsage | None = None,
    ) -> None:
        """Зафиксировать завершённый (успешный или ошибочный) вызов"""
        call = LLMCall(
            provider=provider,
            model=model,
            status=status,
            latency_ms=max(0, latency_ms),
            first_token_ms=first_token_ms,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            created_at=datetime.now(UTC),
        )
        with self._lock:
            self._records.append(call)

    def record_fallback(self) -> None:
        """Отметить, что сработал fallback-провайдер"""
        with self._lock:
            self._fallbacks += 1

    def reset(self) -> None:
        """Очистить метрики (тесты, перезапуск)"""
        with self._lock:
            self._records.clear()
            self._fallbacks = 0

    def snapshot(self) -> dict[str, Any]:
        """Агрегаты за час и сутки + счётчик fallback"""
        with self._lock:
            records = list(self._records)
            fallbacks = self._fallbacks
        return {
            "last_hour": _aggregate(records, hours=1),
            "last_24h": _aggregate(records, hours=24),
            "fallback_used": fallbacks,
            "recorded_at": datetime.now(UTC).isoformat(),
        }


def _percentile(values: list[int], percentile: float) -> int:
    """Ближайший ранг перцентиля (без интерполяции — метрика для мониторинга)"""
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _aggregate(records: list[LLMCall], *, hours: int) -> dict[str, Any]:
    """Свернуть вызовы за окно `hours`"""
    threshold = datetime.now(UTC) - timedelta(hours=hours)
    window = [call for call in records if call.created_at >= threshold]

    latencies = [call.latency_ms for call in window]
    first_tokens = [
        call.first_token_ms for call in window if call.first_token_ms is not None
    ]
    errors = sum(1 for call in window if call.status == "error")

    by_provider: dict[str, dict[str, int | float]] = {}
    for call in window:
        bucket = by_provider.setdefault(
            call.provider,
            {
                "requests": 0,
                "errors": 0,
                "avg_latency_ms": 0.0,
                "total_tokens": 0,
            },
        )
        bucket["requests"] = int(bucket["requests"]) + 1
        bucket["errors"] = int(bucket["errors"]) + (1 if call.status == "error" else 0)
        bucket["total_tokens"] = (
            int(bucket["total_tokens"]) + call.prompt_tokens + call.completion_tokens
        )
        bucket["avg_latency_ms"] = round(
            (float(bucket["avg_latency_ms"]) * (int(bucket["requests"]) - 1) + call.latency_ms)
            / int(bucket["requests"]),
            1,
        )

    return {
        "window_hours": hours,
        "requests": len(window),
        "errors": errors,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
        "p95_latency_ms": _percentile(latencies, 0.95),
        "avg_first_token_ms": (
            round(sum(first_tokens) / len(first_tokens), 1) if first_tokens else 0.0
        ),
        "prompt_tokens": sum(call.prompt_tokens for call in window),
        "completion_tokens": sum(call.completion_tokens for call in window),
        "total_tokens": sum(
            call.prompt_tokens + call.completion_tokens for call in window
        ),
        "by_provider": by_provider,
    }


#: Глобальный реестр, который читает `/admin/analytics`
llm_metrics = LLMMetrics()


class MetricsProvider(LLMProvider):
    """Декоратор провайдера: замеряет латентность и расход токенов"""

    def __init__(self, inner: LLMProvider, registry: LLMMetrics | None = None) -> None:
        self.inner = inner
        self.registry = registry or llm_metrics
        self.name = inner.name
        self.model = inner.model
        self.fallback_name = inner.fallback_name

    def is_configured(self) -> bool:
        return self.inner.is_configured()

    async def ping(self) -> bool:
        return await self.inner.ping()

    def _remember_usage(self) -> None:
        self.last_usage = self.inner.last_usage

    def _finish(
        self, started: float, status: str, first_token_ms: int | None
    ) -> None:
        self._remember_usage()
        self.registry.record(
            provider=self.name,
            model=self.model,
            status=status,
            latency_ms=int((time.perf_counter() - started) * 1000),
            first_token_ms=first_token_ms,
            usage=self.inner.last_usage,
        )

    async def generate(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        started = time.perf_counter()
        try:
            result = await self.inner.generate(
                messages, temperature=temperature, max_tokens=max_tokens
            )
        except LLMUnavailableError:
            self._finish(started, "error", None)
            raise
        self._finish(started, "ok", None)
        return result

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        started = time.perf_counter()
        first_token_ms: int | None = None
        completed = False
        try:
            async for delta in self.inner.stream(
                messages, temperature=temperature, max_tokens=max_tokens
            ):
                if first_token_ms is None:
                    first_token_ms = int((time.perf_counter() - started) * 1000)
                yield delta
            completed = True
        except LLMUnavailableError:
            self._finish(started, "error", first_token_ms)
            raise
        finally:
            if completed:
                self._finish(started, "ok", first_token_ms)

    async def close(self) -> None:
        await self.inner.close()
