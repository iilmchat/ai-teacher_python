"""Конфигурация производительности и nightly (S39)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _yaml(relative: str) -> dict[str, Any]:
    data = yaml.safe_load(_text(relative))
    assert isinstance(data, dict)
    return data


def test_load_test_scenarios_and_budgets() -> None:
    text = _text("backend/scripts/load_test.py")

    assert "name=\"health\"" in text and "rps=20.0" in text
    assert "name=\"tasks\"" in text and "rps=10.0" in text
    assert "name=\"submit\"" in text and "rps=5.0" in text
    assert "budget_ms=300.0" in text
    assert "budget_ms=2000.0" in text


def test_baseline_has_all_scenarios() -> None:
    baseline = json.loads(_text("docs/reports/perf/baseline.json"))

    assert baseline["status"] == "pending_runner"
    assert set(baseline["scenarios"]) == {"health", "tasks", "submit"}
    for scenario in baseline["scenarios"].values():
        assert scenario["rps"] > 0
        assert scenario["budget_p95_ms"] > 0


def test_nightly_runs_all_scenarios_and_compares() -> None:
    text = _text(".github/workflows/perf-nightly.yml")

    assert "preflight.ps1" in text
    assert "-Scenario all" in text
    assert "compare_perf.py" in text
    assert "load-test-night.json" in text


def _write_report(path: Path, p95: float) -> None:
    path.write_text(
        json.dumps(
            {
                "scenarios": [
                    {
                        "scenario": "health",
                        "rps_achieved": 20,
                        "error_rate": 0,
                        "verdict": "PASS",
                        "latency_ms": {"p50": p95 / 2, "p95": p95, "p99": p95},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def _run_compare(tmp_path: Path, p95: float) -> int:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    baseline.write_text(
        json.dumps(
            {
                "scenarios": {
                    "health": {
                        "budget_p95_ms": 300,
                        "measured": 100,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    _write_report(current, p95)
    result = subprocess.run(
        [
            sys.executable,
            "scripts/ci/compare_perf.py",
            "--baseline",
            str(baseline),
            "--current",
            str(current),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode


def test_compare_perf_accepts_within_20_percent(tmp_path: Path) -> None:
    assert _run_compare(tmp_path, 110) == 0


def test_compare_perf_rejects_regression(tmp_path: Path) -> None:
    assert _run_compare(tmp_path, 150) == 1
