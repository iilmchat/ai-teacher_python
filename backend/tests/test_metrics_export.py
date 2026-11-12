"""Метрики как события и общий экспортёр (KI-024).

Проверяем три вещи:
- LLM/кэш отдаются счётчиками/гистограммами в момент события (а не gauge
  из памяти процесса), поэтому значения складываются между воркерами;
- в multiprocess-режиме метрики не регистрируются в реестре рендера —
  иначе `MultiProcessCollector` задвоил бы значения;
- старых per-process gauge (`llm_requests`, `cache_hits`) больше нет.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from prometheus_client import CollectorRegistry, generate_latest
from prometheus_client.multiprocess import MultiProcessCollector

from app.core.metrics import (
    build_registries,
    cache_observed,
    llm_call_observed,
    llm_fallback_observed,
    rate_limit_blocked_observed,
    render_metrics,
    reset_metrics,
    set_dependency_up,
)
from app.services.cache import cache_metrics
from app.services.llm.base import LLMUsage
from app.services.llm.metrics import llm_metrics


@pytest.fixture(autouse=True)
def _clean_metrics() -> None:
    reset_metrics()


def _text() -> str:
    body, content_type = render_metrics()
    assert content_type.startswith("text/plain")
    return body.decode()


def test_llm_call_is_a_counter_and_histogram() -> None:
    llm_call_observed(
        provider="deepseek",
        model="deepseek-chat",
        status="ok",
        latency_ms=1200,
        first_token_ms=300,
        prompt_tokens=20,
        completion_tokens=10,
    )

    text = _text()

    assert 'llm_requests_total{model="deepseek-chat",provider="deepseek",status="ok"} 1.0' in text
    assert 'llm_latency_seconds_count{provider="deepseek"} 1.0' in text
    assert 'llm_latency_seconds_sum{provider="deepseek"} 1.2' in text
    assert 'llm_first_token_seconds_count{provider="deepseek"} 1.0' in text
    assert 'llm_tokens_total{kind="prompt",provider="deepseek"} 20.0' in text
    assert 'llm_tokens_total{kind="completion",provider="deepseek"} 10.0' in text


def test_llm_error_has_own_status_label() -> None:
    llm_call_observed(provider="deepseek", model="m", status="error", latency_ms=5000)

    text = _text()

    assert 'llm_requests_total{model="m",provider="deepseek",status="error"} 1.0' in text
    assert 'llm_tokens_total{kind="completion"' not in text


def test_llm_fallback_counter_has_primary_label() -> None:
    llm_fallback_observed(primary="deepseek")

    assert 'llm_fallbacks_total{primary="deepseek"} 1.0' in _text()


def test_llm_metrics_recording_emits_prometheus_events() -> None:
    llm_metrics.record(
        provider="echo",
        model="echo-model",
        status="ok",
        latency_ms=42,
        usage=LLMUsage(prompt_tokens=3, completion_tokens=4),
    )

    text = _text()

    assert 'llm_requests_total{model="echo-model",provider="echo",status="ok"} 1.0' in text
    assert 'llm_tokens_total{kind="prompt",provider="echo"} 3.0' in text


def test_cache_events_are_counters() -> None:
    cache_observed("hit")
    cache_metrics.record_miss()
    cache_metrics.record_error()

    text = _text()

    assert "cache_hits_total 1.0" in text
    assert "cache_misses_total 1.0" in text
    assert "cache_errors_total 1.0" in text


def test_per_process_gauges_are_gone() -> None:
    llm_call_observed(provider="deepseek", model="m", status="ok", latency_ms=10)
    cache_observed("hit")

    text = _text()

    # Точные имена старых gauge (без _total и гистограмм) не должны встречаться.
    assert "llm_requests{" not in text
    assert "llm_latency_ms" not in text
    assert "cache_hits{" not in text
    assert "llm_failures" not in text


def test_build_registries_single_process_shares_registry() -> None:
    render, metrics = build_registries(multiprocess=False)

    assert render is metrics


def test_build_registries_multiprocess_separates_registries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))
    render, metrics = build_registries(multiprocess=True)

    assert render is not metrics
    # Агрегат отдаёт MultiProcessCollector, своих метрик в реестре рендера нет.
    families = {family.name for family in render.collect()}
    assert "llm_requests_total" not in families


# --- S35-001: multiprocess-агрегация и новые метрики S35-003 ---------------

_WORKER_SNIPPET = """
import sys
from prometheus_client import Counter, Histogram

worker, count = sys.argv[1], int(sys.argv[2])
Counter("mp_test_total", "test counter", ["worker"]).labels(worker).inc(count)
Histogram("mp_test_seconds", "test histogram", buckets=(0.1, 1.0)).observe(
    float(count) / 10.0
)
"""


def _run_worker(tmp_path: Path, worker: str, count: int) -> None:
    env = {**os.environ, "PROMETHEUS_MULTIPROC_DIR": str(tmp_path)}
    subprocess.run(
        [sys.executable, "-c", _WORKER_SNIPPET, worker, str(count)],
        env=env,
        check=True,
        capture_output=True,
    )


def test_multiprocess_counters_and_histograms_are_summed(tmp_path: Path) -> None:
    """Метрики двух «воркеров» не теряются: счётчики и гистограммы суммируются."""
    _run_worker(tmp_path, "worker-a", 3)
    _run_worker(tmp_path, "worker-b", 5)

    registry = CollectorRegistry()
    MultiProcessCollector(registry, path=str(tmp_path))
    text = generate_latest(registry).decode()

    assert 'mp_test_total{worker="worker-a"} 3.0' in text
    assert 'mp_test_total{worker="worker-b"} 5.0' in text
    # Гистограмма: по одному наблюдению на воркер → count = 2, sum = 0.3 + 0.5.
    assert "mp_test_seconds_count 2.0" in text
    assert "mp_test_seconds_sum 0.8" in text


def test_multiprocess_dir_is_reused_without_duplication(tmp_path: Path) -> None:
    """Повторный scrape не задваивает значения (файлы живут, агрегат один)."""
    _run_worker(tmp_path, "worker-a", 2)

    registry = CollectorRegistry()
    MultiProcessCollector(registry, path=str(tmp_path))
    first = generate_latest(registry).decode()
    second = generate_latest(registry).decode()

    assert 'mp_test_total{worker="worker-a"} 2.0' in first
    assert 'mp_test_total{worker="worker-a"} 2.0' in second


def test_metrics_endpoint_can_be_disabled() -> None:
    """При METRICS_ENABLED=false маршрут /metrics не регистрируется (S35-001)."""
    backend_dir = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "METRICS_ENABLED": "false",
        "SECRET_KEY": "x" * 40,
        "DEBUG": "true",
    }
    code = (
        "import app.main as m\n"
        "from app.config import settings\n"
        "print(any(getattr(r, 'path', None) == settings.metrics_path "
        "for r in m.app.routes))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        cwd=backend_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip().splitlines()[-1] == "False"


def test_metrics_endpoint_is_registered_by_default() -> None:
    """По умолчанию /metrics зарегистрирован."""
    from app.config import settings
    from app.main import app

    assert any(
        getattr(route, "path", None) == settings.metrics_path for route in app.routes
    )


def test_rate_limit_blocked_counter_has_scope() -> None:
    """Блокировки лимитов считаются по областям (S35-003)."""
    rate_limit_blocked_observed("login")
    rate_limit_blocked_observed("login")
    rate_limit_blocked_observed("code_execute")

    text = _text()
    assert 'rate_limit_blocked_total{scope="login"} 2.0' in text
    assert 'rate_limit_blocked_total{scope="code_execute"} 1.0' in text


def test_dependency_gauges_are_min_across_workers(tmp_path: Path) -> None:
    """db_up/redis_up — gauges, доступные Prometheus (S35-003)."""
    set_dependency_up(database=True, redis=False)

    text = _text()
    assert "db_up 1.0" in text
    assert "redis_up 0.0" in text


def test_worker_info_exposes_pid() -> None:
    """Каждая реплика публикует app_worker_info{pid} (S35-001)."""
    from app.core.metrics import worker_info_observed

    worker_info_observed(4242)

    assert 'app_worker_info{pid="4242"} 1.0' in _text()
