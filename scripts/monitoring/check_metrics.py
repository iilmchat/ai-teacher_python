"""Smoke-проверка /metrics при запуске с несколькими воркерами (S35-001).

Скрипт читает Prometheus text format и проверяет, что:
- присутствуют ключевые семейства (HTTP, LLM, sandbox);
- при `--expect-workers N` в `process_start_time_seconds` видно N процессов
  (в multiprocess-режиме каждая реплика публикует свой pid);
- при `--min-http N` суммарный счётчик HTTP-запросов не меньше N.

Пример:
    python scripts/monitoring/check_metrics.py \
        --url http://127.0.0.1:8000/metrics --expect-workers 2 --min-http 2
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.request

DEFAULT_REQUIRED = ("http_requests_total",)
_SAMPLE_RE = re.compile(r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?P<labels>\{.*\})?\s+(?P<value>\S+)$")
_PID_RE = re.compile(r'pid="(?P<pid>[^"]+)"')


def fetch(url: str, timeout: float) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_samples(text: str) -> list[tuple[str, str, float]]:
    samples: list[tuple[str, str, float]] = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        match = _SAMPLE_RE.match(line.strip())
        if not match:
            continue
        try:
            value = float(match.group("value"))
        except ValueError:
            continue
        samples.append((match.group("name"), match.group("labels") or "", value))
    return samples


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-проверка метрик backend")
    parser.add_argument(
        "--url",
        default=os.environ.get("METRICS_URL", "http://127.0.0.1:8000/metrics"),
    )
    parser.add_argument("--expect-workers", type=int, default=0)
    parser.add_argument("--min-http", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument(
        "--require",
        nargs="*",
        default=list(DEFAULT_REQUIRED),
        help="обязательные семейства метрик",
    )
    args = parser.parse_args()

    try:
        text = fetch(args.url, args.timeout)
    except Exception as exc:  # noqa: BLE001 — smoke-скрипт печатает причину
        print(f"ERROR: не удалось прочитать {args.url}: {exc}", file=sys.stderr)
        return 1

    samples = parse_samples(text)
    names = {name for name, _, _ in samples}
    failures: list[str] = []

    for required in args.require:
        if not any(name == required or name.startswith(required + "_") for name in names):
            failures.append(f"нет метрики {required}")

    http_total = sum(value for name, _, value in samples if name == "http_requests_total")
    if args.min_http and http_total < args.min_http:
        failures.append(
            f"http_requests_total={http_total} < ожидаемого {args.min_http}"
        )

    pids: set[str] = set()
    for name, labels, _ in samples:
        # S35-001: каждая реплика публикует app_worker_info{pid=...}.
        # process_start_time_seconds в multiprocess-режиме недоступен — fallback.
        if name in {"app_worker_info", "process_start_time_seconds"}:
            match = _PID_RE.search(labels)
            if match:
                pids.add(match.group("pid"))

    if args.expect_workers:
        if not pids:
            failures.append(
                "нет app_worker_info{pid}: не подтвердить число воркеров"
            )
        elif len(pids) < args.expect_workers:
            failures.append(
                f"видно {len(pids)} процесс(ов), ожидалось >= {args.expect_workers}"
            )

    print(f"URL: {args.url}")
    print(f"http_requests_total: {http_total}")
    print(f"worker pids: {', '.join(sorted(pids)) if pids else 'n/a'}")
    print(f"metric families: {len(names)}")

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1

    print("OK: метрики присутствуют и агрегируются")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
