"""Prometheus-метрики (S25-002).

HTTP-метрики считаются middleware; метрики LLM/кэша/пула БД — «мостиком» из
существующих in-memory счётчиков процесса (`llm_metrics`, `cache_metrics`,
`engine.pool`) в момент scrape: сервисы не переписываем, но значения видны в
Prometheus. Метрики песочницы обновляет `SandboxedExecutor` через
`sandbox_observed`.

Эндпоинт `/metrics` без авторизации — для внутренней сети; в nginx наружу не
публикуется (`docs/DESIGN_ADMIN_AND_OPS.md` §monitoring).
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

import structlog
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)

#: Отдельный реестр: не тянет process/platform-коллекторы по умолчанию и не
#: конфликтует при повторной регистрации в тестах.
registry = CollectorRegistry()

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "HTTP-запросы по методу, шаблону пути и статусу",
    ["method", "path", "status"],
    registry=registry,
)
HTTP_DURATION = Histogram(
    "http_request_duration_seconds",
    "Длительность HTTP-запросов",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=registry,
)

SANDBOX_RUNS = Counter(
    "sandbox_runs_total",
    "Запуски песочницы по режиму и результату",
    ["mode", "result"],
    registry=registry,
)
SANDBOX_DURATION = Histogram(
    "sandbox_duration_seconds",
    "Длительность исполнения в песочнице",
    ["mode"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
    registry=registry,
)
SANDBOX_TIMEOUTS = Counter(
    "sandbox_timeouts_total",
    "Таймауты песочницы",
    ["mode"],
    registry=registry,
)

# Метрики, которые нельзя накапливать в Prometheus напрямую (значения живут в
# счётчиках процесса) — отдаём как gauge на момент scrape.
LLM_REQUESTS = Gauge("llm_requests", "LLM-вызовы в процессе", ["provider"], registry=registry)
LLM_FAILURES = Gauge("llm_failures", "Ошибки LLM в процессе", ["provider"], registry=registry)
LLM_FALLBACKS = Gauge("llm_fallbacks", "Fallback-переключения LLM", registry=registry)
LLM_LATENCY_MS = Gauge(
    "llm_latency_ms", "Средняя латентность LLM, мс", ["provider"], registry=registry
)
LLM_TOKENS = Gauge("llm_tokens", "Токены LLM в процессе", ["kind"], registry=registry)

CACHE_HITS = Gauge("cache_hits", "Попадания в кэш (процесс)", registry=registry)
CACHE_MISSES = Gauge("cache_misses", "Промахи кэша (процесс)", registry=registry)
CACHE_ERRORS = Gauge("cache_errors", "Ошибки кэша (процесс)", registry=registry)

DB_POOL = Gauge(
    "db_pool_connections",
    "Соединения пула БД",
    ["state"],
    registry=registry,
)
DB_POOL_SIZE = Gauge("db_pool_size", "Размер пула БД", registry=registry)


class HTTPMetricsMiddleware(BaseHTTPMiddleware):
    """Счётчики/гистограмма HTTP по шаблону маршрута (без uuid в label)"""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            path = _route_template(request)
            HTTP_REQUESTS.labels(request.method, path, "500").inc()
            HTTP_DURATION.labels(request.method, path).observe(
                time.perf_counter() - started
            )
            raise

        path = _route_template(request)
        HTTP_REQUESTS.labels(request.method, path, str(response.status_code)).inc()
        HTTP_DURATION.labels(request.method, path).observe(
            time.perf_counter() - started
        )
        return response


def _route_template(request: Request) -> str:
    """Шаблон пути (`/tasks/{task_id}`) вместо конкретного uuid"""
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    if isinstance(template, str) and template:
        return template
    return request.url.path


def sandbox_observed(
    *, mode: str, duration_s: float, timed_out: bool, failed: bool
) -> None:
    """Зафиксировать запуск песочницы (S25-002)"""
    SANDBOX_DURATION.labels(mode).observe(max(duration_s, 0.0))
    result = "timeout" if timed_out else ("error" if failed else "ok")
    SANDBOX_RUNS.labels(mode, result).inc()
    if timed_out:
        SANDBOX_TIMEOUTS.labels(mode).inc()


def _refresh_process_gauges() -> None:
    """Снять in-memory счётчики процесса в gauge'ы перед scrape"""
    from app.db.database import engine
    from app.services.cache import cache_metrics
    from app.services.llm.metrics import llm_metrics

    try:
        llm_snapshot = llm_metrics.snapshot()
        provider = str(llm_snapshot.get("provider") or "unknown")
        LLM_REQUESTS.labels(provider).set(float(llm_snapshot.get("total_calls") or 0))
        LLM_FAILURES.labels(provider).set(float(llm_snapshot.get("errors") or 0))
        LLM_LATENCY_MS.labels(provider).set(
            float(llm_snapshot.get("avg_latency_ms") or 0)
        )
        LLM_FALLBACKS.set(float(llm_snapshot.get("fallbacks") or 0))
        LLM_TOKENS.labels("prompt").set(float(llm_snapshot.get("prompt_tokens") or 0))
        LLM_TOKENS.labels("completion").set(
            float(llm_snapshot.get("completion_tokens") or 0)
        )
    except Exception as exc:  # noqa: BLE001 — метрики не должны ломать scrape
        logger.warning("metrics_llm_bridge_failed", error=str(exc))

    try:
        cache_snapshot = cache_metrics.snapshot()
        CACHE_HITS.set(float(cache_snapshot.get("hits") or 0))
        CACHE_MISSES.set(float(cache_snapshot.get("misses") or 0))
        CACHE_ERRORS.set(float(cache_snapshot.get("errors") or 0))
    except Exception as exc:  # noqa: BLE001
        logger.warning("metrics_cache_bridge_failed", error=str(exc))

    try:
        pool = engine.pool
        DB_POOL.labels("checked_out").set(float(pool.checkedout()))  # type: ignore[attr-defined]
        DB_POOL_SIZE.set(float(pool.size()))  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — драйвер/пул может не поддерживать
        pass


def render_metrics() -> tuple[bytes, str]:
    """Сформировать ответ Prometheus: (тело, content-type)"""
    _refresh_process_gauges()
    return generate_latest(registry), CONTENT_TYPE_LATEST


def reset_metrics() -> None:
    """Сбросить HTTP/sandbox-метрики (тесты)"""
    for metric in (HTTP_REQUESTS, HTTP_DURATION, SANDBOX_RUNS, SANDBOX_DURATION, SANDBOX_TIMEOUTS):
        metric.clear()
