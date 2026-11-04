"""Prometheus-метрики (S25-002) и общий экспортёр (KI-024).

HTTP-метрики считает middleware. Метрики LLM, кэша, песочницы и retention —
счётчики/гистограммы, которые инкрементируются в момент события: сервисы
вызывают `llm_call_observed`, `cache_observed`, `sandbox_observed`, а
retention — `RETENTION_RUNS`/`RETENTION_ROWS`. Поэтому значения корректно
складываются при нескольких воркерах — в multiprocess-режиме prometheus_client
(`PROMETHEUS_MULTIPROC_DIR`) любая реплика отдаёт общий агрегат, а Prometheus
складывает по `instance`/`pod`. Прежний вариант (gauge из in-memory счётчиков
процесса) показан в KI-024 и убран.

Песочница обновляет метрики через `SandboxedExecutor`; пул БД снимается с
`engine.pool` в момент scrape (это состояние процесса, а не событие).

Эндпоинт `/metrics` без авторизации — для внутренней сети; в nginx наружу не
публикуется (`docs/DESIGN_ADMIN_AND_OPS.md` §10).
"""

from __future__ import annotations

import os
import time
from collections.abc import Awaitable, Callable
from typing import Any

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

#: Каталог multiprocess-режима prometheus_client (KI-024). Не задан — обычный
#: режим одного процесса (значения читаются из его реестра).
MULTIPROCESS_ENV = "PROMETHEUS_MULTIPROC_DIR"


def multiprocess_enabled() -> bool:
    """Включён ли multiprocess-режим (API запущен с несколькими воркерами)"""
    return bool(os.environ.get(MULTIPROCESS_ENV))


def prepare_multiprocess_dir() -> None:
    """Создать каталог multiprocess-режима (идемпотентно).

    Чистить каталог должен entrypoint **до** старта воркеров: удаление файлов
    внутри процесса стёрло бы значения уже работающих реплик.
    """
    directory = os.environ.get(MULTIPROCESS_ENV)
    if directory:
        os.makedirs(directory, exist_ok=True)


def build_registries(
    *, multiprocess: bool
) -> tuple[CollectorRegistry, CollectorRegistry]:
    """Создать пару реестров: (реестр для рендера, реестр для метрик).

    В multiprocess-режиме метрики нельзя регистрировать в реестре рендера:
    агрегат отдаёт `MultiProcessCollector` из файлов каталога, и собственные
    значения процесса задвоили бы счётчики.
    """
    render = CollectorRegistry()
    if not multiprocess:
        return render, render

    from prometheus_client.multiprocess import MultiProcessCollector

    MultiProcessCollector(render)  # type: ignore[no-untyped-call]
    return render, CollectorRegistry()


#: Реестр, который рендерится в `/metrics`
prepare_multiprocess_dir()
registry, _metric_registry = build_registries(multiprocess=multiprocess_enabled())

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "HTTP-запросы по методу, шаблону пути и статусу",
    ["method", "path", "status"],
    registry=_metric_registry,
)
HTTP_DURATION = Histogram(
    "http_request_duration_seconds",
    "Длительность HTTP-запросов",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=_metric_registry,
)

SANDBOX_RUNS = Counter(
    "sandbox_runs_total",
    "Запуски песочницы по режиму и результату",
    ["mode", "result"],
    registry=_metric_registry,
)
SANDBOX_DURATION = Histogram(
    "sandbox_duration_seconds",
    "Длительность исполнения в песочнице",
    ["mode"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
    registry=_metric_registry,
)
SANDBOX_TIMEOUTS = Counter(
    "sandbox_timeouts_total",
    "Таймауты песочницы",
    ["mode"],
    registry=_metric_registry,
)

# LLM: события, а не снимок процесса (KI-024).
LLM_REQUESTS = Counter(
    "llm_requests_total",
    "Вызовы LLM по провайдеру, модели и результату",
    ["provider", "model", "status"],
    registry=_metric_registry,
)
LLM_LATENCY = Histogram(
    "llm_latency_seconds",
    "Полная латентность вызова LLM",
    ["provider"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
    registry=_metric_registry,
)
LLM_FIRST_TOKEN = Histogram(
    "llm_first_token_seconds",
    "Время до первого токена в потоке",
    ["provider"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
    registry=_metric_registry,
)
LLM_TOKENS = Counter(
    "llm_tokens_total",
    "Токены LLM по провайдеру и виду (prompt/completion)",
    ["provider", "kind"],
    registry=_metric_registry,
)
LLM_FALLBACKS = Counter(
    "llm_fallbacks_total",
    "Переключения на резервного провайдера",
    ["primary"],
    registry=_metric_registry,
)

# Кэш: события кэша (KI-024).
CACHE_HITS = Counter(
    "cache_hits_total", "Попадания в кэш", registry=_metric_registry
)
CACHE_MISSES = Counter(
    "cache_misses_total", "Промахи кэша", registry=_metric_registry
)
CACHE_SETS = Counter(
    "cache_sets_total", "Записи в кэш", registry=_metric_registry
)
CACHE_INVALIDATIONS = Counter(
    "cache_invalidations_total", "Инвалидации кэша", registry=_metric_registry
)
CACHE_ERRORS = Counter(
    "cache_errors_total", "Ошибки кэша", registry=_metric_registry
)

# Retention (KI-025): число прогонов и удалённых строк по таблицам. Счётчики
# (а не gauge) — значения накапливаются и суммируются Prometheus'ом. Пишут и
# планировщик, и CLI (`apply_retention`).
RETENTION_RUNS = Counter(
    "retention_runs_total",
    "Прогоны retention по таблице и результату",
    ["table", "result"],
    registry=_metric_registry,
)
RETENTION_ROWS = Counter(
    "retention_rows_deleted_total",
    "Удалённые retention-строки",
    ["table"],
    registry=_metric_registry,
)

# Пул БД — состояние процесса на момент scrape.
DB_POOL = Gauge(
    "db_pool_connections",
    "Соединения пула БД",
    ["state"],
    multiprocess_mode="livesum",
    registry=_metric_registry,
)
DB_POOL_SIZE = Gauge(
    "db_pool_size",
    "Размер пула БД",
    multiprocess_mode="max",
    registry=_metric_registry,
)

#: Информация о сборке: app_build_info{version="0.3.3"} 1
BUILD_INFO = Gauge(
    "app_build_info",
    "Версия приложения",
    ["version"],
    multiprocess_mode="max",
    registry=_metric_registry,
)

_CACHE_COUNTERS: dict[str, Counter] = {
    "hit": CACHE_HITS,
    "miss": CACHE_MISSES,
    "set": CACHE_SETS,
    "invalidation": CACHE_INVALIDATIONS,
    "error": CACHE_ERRORS,
}


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


def llm_call_observed(
    *,
    provider: str,
    model: str,
    status: str,
    latency_ms: int,
    first_token_ms: int | None = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """Зафиксировать вызов LLM (KI-024: событие, а не gauge процесса)"""
    provider_label = provider or "unknown"
    LLM_REQUESTS.labels(provider_label, model or "unknown", status).inc()
    LLM_LATENCY.labels(provider_label).observe(max(latency_ms, 0) / 1000)
    if first_token_ms is not None:
        LLM_FIRST_TOKEN.labels(provider_label).observe(max(first_token_ms, 0) / 1000)
    if prompt_tokens:
        LLM_TOKENS.labels(provider_label, "prompt").inc(prompt_tokens)
    if completion_tokens:
        LLM_TOKENS.labels(provider_label, "completion").inc(completion_tokens)


def llm_fallback_observed(*, primary: str) -> None:
    """Зафиксировать переключение на резервного провайдера"""
    LLM_FALLBACKS.labels(primary or "unknown").inc()


def cache_observed(kind: str) -> None:
    """Зафиксировать событие кэша: hit/miss/set/invalidation/error"""
    counter = _CACHE_COUNTERS.get(kind)
    if counter is not None:
        counter.inc()


def set_build_info(version: str) -> None:
    """Отметить версию сборки (`app_build_info{version=...}`)"""
    BUILD_INFO.labels(version).set(1)


def _refresh_db_pool_gauges() -> None:
    """Снять состояние пула БД в gauge'ы перед scrape"""
    from app.db.database import engine

    try:
        pool = engine.pool
        DB_POOL.labels("checked_out").set(float(pool.checkedout()))  # type: ignore[attr-defined]
        DB_POOL_SIZE.set(float(pool.size()))  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — драйвер/пул может не поддерживать
        pass


def render_metrics() -> tuple[bytes, str]:
    """Сформировать ответ Prometheus: (тело, content-type)"""
    _refresh_db_pool_gauges()
    return generate_latest(registry), CONTENT_TYPE_LATEST


def _reset_metric(metric: Any) -> None:
    """Обнулить метрику.

    `clear()` в prometheus_client удаляет только наборы меток: для метрик без
    меток он молча ничего не делает, поэтому значение обнуляем напрямую.
    Нужно только тестам (между ними счётчики иначе «протекают»).
    """
    metric.clear()
    if metric._labelnames:
        return
    setter = getattr(getattr(metric, "_value", None), "set", None)
    if callable(setter):
        setter(0)


def reset_metrics() -> None:
    """Сбросить счётчики/гистограммы (тесты)"""
    for metric in (
        HTTP_REQUESTS,
        HTTP_DURATION,
        SANDBOX_RUNS,
        SANDBOX_DURATION,
        SANDBOX_TIMEOUTS,
        LLM_REQUESTS,
        LLM_LATENCY,
        LLM_FIRST_TOKEN,
        LLM_TOKENS,
        LLM_FALLBACKS,
        CACHE_HITS,
        CACHE_MISSES,
        CACHE_SETS,
        CACHE_INVALIDATIONS,
        CACHE_ERRORS,
        RETENTION_RUNS,
        RETENTION_ROWS,
        DB_POOL,
        DB_POOL_SIZE,
        BUILD_INFO,
    ):
        _reset_metric(metric)
