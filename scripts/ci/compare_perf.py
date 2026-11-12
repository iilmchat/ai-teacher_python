"""Сравнение ночного perf-прогона с baseline (S39-001).

Правила:
- p95 сценария не выше бюджета (дублирует load_test, но полезно в отчёте);
- если в baseline есть измеренный p95, рост более чем на 20% — регресс;
- если baseline ещё пуст (`measured: null`), сравнение только по бюджетам.

Код возврата: 0 — ок; 1 — регресс/превышение; 2 — неверные файлы.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: не удалось прочитать {path}: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    if not isinstance(data, dict):
        print(f"ERROR: {path} должен содержать объект", file=sys.stderr)
        raise SystemExit(2)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Perf baseline regression")
    parser.add_argument("--baseline", default="docs/reports/perf/baseline.json")
    parser.add_argument("--current", default="docs/reports/perf/load-test-night.json")
    parser.add_argument("--max-regression", type=float, default=0.20)
    args = parser.parse_args()

    baseline = load(Path(args.baseline))
    current = load(Path(args.current))
    current_scenarios = {item["scenario"]: item for item in current.get("scenarios", [])}

    failures: list[str] = []
    for name, rules in baseline.get("scenarios", {}).items():
        measured = current_scenarios.get(name)
        if measured is None:
            failures.append(f"{name}: нет результата в отчёте")
            continue

        p95 = float(measured["latency_ms"]["p95"])
        budget = float(rules.get("budget_p95_ms", 0))
        if budget and p95 > budget:
            failures.append(f"{name}: p95 {p95:.0f} мс > бюджет {budget:.0f} мс")

        base_p95 = rules.get("measured")
        if base_p95 is not None and float(base_p95) > 0:
            limit = float(base_p95) * (1 + args.max_regression)
            if p95 > limit:
                failures.append(
                    f"{name}: p95 {p95:.0f} мс > baseline {float(base_p95):.0f} мс +"
                    f" {args.max_regression * 100:.0f}%"
                )

    print("Perf scenarios:")
    for name, item in current_scenarios.items():
        lat = item["latency_ms"]
        print(
            f"  {name:8} rps={item['rps_achieved']:5.1f} "
            f"p50={lat['p50']:7.1f} p95={lat['p95']:7.1f} "
            f"err={item['error_rate'] * 100:5.2f}% {item['verdict']}"
        )

    if failures:
        print("PERF REGRESSION:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    if all(rule.get("measured") is None for rule in baseline.get("scenarios", {}).values()):
        print("OK: бюджеты соблюдены; baseline ещё не заполнен (ждёт первого прогона).")
    else:
        print("OK: бюджеты и baseline соблюдены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
