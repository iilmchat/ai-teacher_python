"""Конфигурация мониторинга как код (S35-003/S35-004).

Проверки без запуска Prometheus/Grafana:
- `prometheus.yml` ссылается на правила и scrape'ит backend;
- в `alerts.yml` есть обязательные алерты с severity/summary/runbook;
- recording rules содержат имена для SLO;
- Grafana-дашборд — валидный JSON с панелями и выражениями.

Синтаксис PromQL дополнительно валидируется `promtool` в CI
(`scripts/monitoring/validate_prometheus.*`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
PROMETHEUS_DIR = ROOT / "deploy" / "monitoring" / "prometheus"
DASHBOARDS_DIR = ROOT / "deploy" / "monitoring" / "grafana" / "dashboards"

REQUIRED_ALERTS = {
    "High5xxRate",
    "DatabaseDown",
    "SandboxTimeoutsSpike",
    "LLMSlowResponses",
    "BackendDown",
    "RateLimitSpike",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), path
    return data


def _alerts() -> dict[str, dict[str, Any]]:
    data = _load_yaml(PROMETHEUS_DIR / "rules" / "alerts.yml")
    result: dict[str, dict[str, Any]] = {}
    for group in data["groups"]:
        for rule in group["rules"]:
            if "alert" in rule:
                result[rule["alert"]] = rule
    return result


def test_prometheus_scrapes_backend_and_loads_rules() -> None:
    config = _load_yaml(PROMETHEUS_DIR / "prometheus.yml")

    assert any(
        "/rules/alerts.yml" in path for path in config["rule_files"]
    )
    targets = [
        target
        for scrape in config["scrape_configs"]
        for static in scrape.get("static_configs", [])
        for target in static.get("targets", [])
    ]
    assert "backend:8000" in targets


def test_required_alerts_exist_and_have_runbook() -> None:
    alerts = _alerts()

    assert REQUIRED_ALERTS <= set(alerts)
    for name in REQUIRED_ALERTS:
        rule = alerts[name]
        assert rule["expr"].strip(), name
        assert rule["labels"]["severity"] in {"warning", "critical"}, name
        assert rule["annotations"]["summary"], name
        assert rule["annotations"]["runbook_url"].startswith("docs/MONITORING.md"), name


def test_alert_expressions_cover_5xx_db_sandbox_and_llm() -> None:
    alerts = _alerts()

    assert "5.." in alerts["High5xxRate"]["expr"]
    assert "db_up" in alerts["DatabaseDown"]["expr"]
    assert "sandbox_timeouts_total" in alerts["SandboxTimeoutsSpike"]["expr"]
    assert "llm_latency_seconds_bucket" in alerts["LLMSlowResponses"]["expr"]


def test_recording_rules_define_slo_names() -> None:
    data = _load_yaml(PROMETHEUS_DIR / "rules" / "recording.yml")
    names = {
        rule["record"]
        for group in data["groups"]
        for rule in group["rules"]
        if "record" in rule
    }

    assert "job:http_errors_5xx:ratio5m" in names
    assert "job:http_latency_p95_5m" in names
    assert "provider:llm_latency_p95_5m" in names


def test_grafana_dashboard_is_valid_and_has_panels() -> None:
    files = sorted(DASHBOARDS_DIR.glob("*.json"))
    assert files, "дашборды не найдены"

    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["title"]
        assert data["uid"]
        panels = data["panels"]
        assert panels
        for panel in panels:
            assert panel["type"]
            assert panel["title"]
            assert any(
                str(target.get("expr", "")).strip()
                for target in panel.get("targets", [])
            )
