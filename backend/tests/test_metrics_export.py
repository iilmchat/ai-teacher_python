"""Метрики как события и общий экспортёр (KI-024).

Проверяем три вещи:
- LLM/кэш отдаются счётчиками/гистограммами в момент события (а не gauge
  из памяти процесса), поэтому значения складываются между воркерами;
- в multiprocess-режиме метрики не регистрируются в реестре рендера —
  иначе `MultiProcessCollector` задвоил бы значения;
- старых per-process gauge (`llm_requests`, `cache_hits`) больше нет.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.metrics import (
    build_registries,
    cache_observed,
    llm_call_observed,
    llm_fallback_observed,
    render_metrics,
    reset_metrics,
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
