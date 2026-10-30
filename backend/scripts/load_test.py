"""S19-006: нагрузочный тест API на asyncio + httpx (k6/locust недоступны).

Почему свой раннер:
- PyPI на машине заблокирован, k6 (Go-binary) и locust (Python-пакет) не
  поставить; httpx и asyncio уже есть в окружении backend;
- нужен фиксированный RPS и точные p50/p95/p99 при малой длительности,
  что проще контролировать открытым циклом «слот каждые 1/RPS секунд».

Сценарии и бюджеты (p95):
- ``health`` — GET /api/v1/health, 50 RPS, бюджет 300 мс;
- ``tasks``  — GET /api/v1/tasks (под токеном), 20 RPS, бюджет 300 мс;
- ``submit`` — POST /api/v1/tasks/{id}/submit (правильное решение, песочница),
  5 RPS, бюджет 2000 мс.

Код завершения 1, если в любом сценарии p95 > бюджета или error rate > 1%.

Примеры:
    python scripts/load_test.py --scenario all --duration 25 \
        --json-out ../docs/reports/sprint-19/load-test.json
    python scripts/load_test.py --scenario health --rps 100 --duration 10
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import platform
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
PASSWORD = "password123"
ERROR_RATE_LIMIT = 0.01  # 1%

#: Задача из seed-набора и её эталонное решение (S19-006, brief).
SEEDED_TASK_TITLE = "Сумма двух чисел"
SEEDED_TASK_SOLUTION = "a = int(input())\nb = int(input())\nprint(a + b)\n"


@dataclass(slots=True)
class Scenario:
    """Описание нагрузочного сценария."""

    name: str
    method: str
    path: str
    rps: float
    budget_ms: float
    concurrency: int
    needs_auth: bool = False
    body_template: dict[str, Any] | None = None

    @property
    def interval(self) -> float:
        return 1.0 / self.rps


SCENARIOS: dict[str, Scenario] = {
    "health": Scenario(
        name="health",
        method="GET",
        path="/api/v1/health",
        rps=50.0,
        budget_ms=300.0,
        concurrency=20,
    ),
    "tasks": Scenario(
        name="tasks",
        method="GET",
        path="/api/v1/tasks",
        rps=20.0,
        budget_ms=300.0,
        concurrency=20,
        needs_auth=True,
    ),
    "submit": Scenario(
        name="submit",
        method="POST",
        path="/api/v1/tasks/{task_id}/submit",
        rps=5.0,
        budget_ms=2000.0,
        concurrency=5,
        needs_auth=True,
        body_template={"code": SEEDED_TASK_SOLUTION},
    ),
}


@dataclass(slots=True)
class UserSession:
    """Зарегистрированный нагрузочный пользователь."""

    username: str
    token: str


@dataclass(slots=True)
class ScenarioResult:
    """Результат одного сценария."""

    name: str
    rps_target: float
    duration_s: float
    total: int
    errors: int
    latencies_ms: list[float]
    status_codes: dict[str, int]
    error_samples: list[str]
    budget_ms: float
    wall_s: float = 0.0
    warnings: list[str] = field(default_factory=list)

    @property
    def error_rate(self) -> float:
        return self.errors / self.total if self.total else 0.0

    @property
    def achieved_rps(self) -> float:
        return self.total / self.wall_s if self.wall_s else 0.0

    def percentile(self, percentile: float) -> float:
        if not self.latencies_ms:
            return 0.0
        ordered = sorted(self.latencies_ms)
        if len(ordered) == 1:
            return ordered[0]
        rank = (len(ordered) - 1) * percentile / 100.0
        lower = math.floor(rank)
        upper = math.ceil(rank)
        if lower == upper:
            return ordered[lower]
        weight = rank - lower
        return ordered[lower] * (1.0 - weight) + ordered[upper] * weight

    @property
    def p50(self) -> float:
        return self.percentile(50)

    @property
    def p95(self) -> float:
        return self.percentile(95)

    @property
    def p99(self) -> float:
        return self.percentile(99)

    @property
    def mean(self) -> float:
        return statistics.fmean(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def maximum(self) -> float:
        return max(self.latencies_ms) if self.latencies_ms else 0.0

    def verdict(self) -> str:
        if self.p95 > self.budget_ms:
            return "FAIL (p95)"
        if self.error_rate > ERROR_RATE_LIMIT:
            return "FAIL (errors)"
        return "PASS"

    def as_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.name,
            "rps_target": self.rps_target,
            "rps_achieved": round(self.achieved_rps, 2),
            "duration_s": self.duration_s,
            "total_requests": self.total,
            "errors": self.errors,
            "error_rate": round(self.error_rate, 4),
            "status_codes": dict(sorted(self.status_codes.items())),
            "latency_ms": {
                "mean": round(self.mean, 2),
                "p50": round(self.p50, 2),
                "p95": round(self.p95, 2),
                "p99": round(self.p99, 2),
                "max": round(self.maximum, 2),
            },
            "budget_p95_ms": self.budget_ms,
            "verdict": self.verdict(),
            "warnings": self.warnings,
            "error_samples": self.error_samples,
        }


class _Collector:
    """Потокобезопасность не нужна: всё живёт в одном event loop."""

    def __init__(self, record: bool) -> None:
        self.record = record
        self.latencies_ms: list[float] = []
        self.status_codes: Counter[str] = Counter()
        self.errors = 0
        self.total = 0
        self.error_samples: list[str] = []
        self.warnings: list[str] = []

    def add_success(self, status_code: int, latency_ms: float) -> None:
        self.total += 1
        self.status_codes[str(status_code)] += 1
        if self.record:
            self.latencies_ms.append(latency_ms)
        if status_code >= 400:
            self.errors += 1
            if len(self.error_samples) < 5:
                self.error_samples.append(f"HTTP {status_code}")

    def add_exception(self, exc: BaseException, latency_ms: float) -> None:
        self.total += 1
        self.status_codes["exception"] += 1
        self.errors += 1
        if self.record:
            self.latencies_ms.append(latency_ms)
        if len(self.error_samples) < 5:
            self.error_samples.append(f"{type(exc).__name__}: {exc}"[:160])


async def _wait_for_health(client: httpx.AsyncClient, timeout: float = 30.0) -> None:
    """Дождаться готовности backend (lifespan + seed)."""
    deadline = time.monotonic() + timeout
    last_error: str = "timeout"
    while time.monotonic() < deadline:
        try:
            response = await client.get("/api/v1/health")
            if response.status_code == 200:
                return
            last_error = f"HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            last_error = str(exc)
        await asyncio.sleep(0.25)
    raise RuntimeError(f"backend не готов за {timeout} с: {last_error}")


async def _register_and_login(
    client: httpx.AsyncClient, username: str
) -> UserSession:
    """Создать уникального пользователя и получить access-токен."""
    register = await client.post(
        "/api/v1/auth/register",
        json={
            # example.com — валидный для EmailStr домен (special-use TLD не проходит)
            "email": f"{username}@example.com",
            "username": username,
            "password": PASSWORD,
        },
    )
    # 400 — пользователь уже есть (повторный прогон с тем же суффиксом)
    if register.status_code not in (201, 400):
        raise RuntimeError(
            f"регистрация {username} не удалась: {register.status_code} "
            f"{register.text[:200]}"
        )

    login = await client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": PASSWORD},
    )
    if login.status_code != 200:
        raise RuntimeError(
            f"логин {username} не удался: {login.status_code} {login.text[:200]}"
        )
    token: str = login.json()["access_token"]
    return UserSession(username=username, token=token)


async def _prepare_users(
    client: httpx.AsyncClient, count: int
) -> list[UserSession]:
    """Несколько пользователей: submit пишет progress, без размазывания — contention."""
    suffix = f"{int(time.time())}_{os.getpid()}"
    users: list[UserSession] = []
    for index in range(count):
        username = f"load_{suffix}_{index}"
        users.append(await _register_and_login(client, username))
    return users


async def _pick_task_id(
    client: httpx.AsyncClient, user: UserSession
) -> tuple[str, str, str]:
    """Выбрать seed-задачу и решение; вернуть (id, title, code)."""
    response = await client.get(
        "/api/v1/tasks", headers={"Authorization": f"Bearer {user.token}"}
    )
    response.raise_for_status()
    tasks: list[dict[str, Any]] = response.json()
    if not tasks:
        raise RuntimeError("каталог задач пуст: backend не засеян (SEED_ON_START?)")
    for task in tasks:
        if task.get("title") == SEEDED_TASK_TITLE:
            solution = SEEDED_TASK_SOLUTION
            return str(task["id"]), str(task["title"]), solution
    # Fallback: любая задача, код заведомо неверный, но песочница исполняет
    # все тест-кейсы — нагрузочный профиль тот же.
    return str(tasks[0]["id"]), str(tasks[0]["title"]), "print(1)\n"


def _request_parts(
    scenario: Scenario,
    user: UserSession | None,
    task_id: str,
    solution: str,
) -> tuple[str, dict[str, str], dict[str, Any] | None]:
    """Собрать (path, headers, json) для одного запроса сценария."""
    headers: dict[str, str] = {}
    if scenario.needs_auth and user is not None:
        headers["Authorization"] = f"Bearer {user.token}"
        path = scenario.path.format(task_id=task_id)
    else:
        path = scenario.path
    body: dict[str, Any] | None = None
    if scenario.body_template is not None:
        body = dict(scenario.body_template)
        body["code"] = solution
    return path, headers, body


async def _drive(
    client: httpx.AsyncClient,
    scenario: Scenario,
    users: list[UserSession],
    task_id: str,
    solution: str,
    duration: float,
    record: bool,
) -> _Collector:
    """Открытый цикл: новый запрос в слот каждые 1/RPS секунд."""
    collector = _Collector(record=record)
    semaphore = asyncio.Semaphore(scenario.concurrency)
    pending: list[asyncio.Task[None]] = []
    interval = scenario.interval
    request_index = 0

    async def worker(index: int) -> None:
        user = users[index % len(users)] if users else None
        path, headers, body = _request_parts(scenario, user, task_id, solution)
        async with semaphore:
            started = time.perf_counter()
            try:
                response = await client.request(
                    scenario.method, path, headers=headers, json=body
                )
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                collector.add_success(response.status_code, elapsed_ms)
            except Exception as exc:  # noqa: BLE001 — любая ошибка клиента — error
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                collector.add_exception(exc, elapsed_ms)

    started_at = time.perf_counter()
    deadline = started_at + duration
    next_slot = started_at
    while True:
        now = time.perf_counter()
        if now >= deadline:
            break
        if next_slot > now:
            await asyncio.sleep(next_slot - now)
        pending.append(asyncio.create_task(worker(request_index)))
        request_index += 1
        next_slot += interval

    if pending:
        await asyncio.gather(*pending)
    collector.wall_s = time.perf_counter() - started_at
    return collector


async def _run_scenario(
    client: httpx.AsyncClient,
    scenario: Scenario,
    users: list[UserSession],
    task_id: str,
    solution: str,
    duration: float,
    warmup: float,
) -> ScenarioResult:
    """Прогрев (не учитывается) + измеряемый прогон."""
    print(
        f"[load] {scenario.name}: target={scenario.rps:g} RPS, "
        f"{scenario.concurrency} concurrency, {duration:g} с, "
        f"budget p95={scenario.budget_ms:g} мс"
    )
    if warmup > 0:
        await _drive(
            client, scenario, users, task_id, solution, warmup, record=False
        )

    collector = await _drive(
        client, scenario, users, task_id, solution, duration, record=True
    )
    return ScenarioResult(
        name=scenario.name,
        rps_target=scenario.rps,
        duration_s=duration,
        total=collector.total,
        errors=collector.errors,
        latencies_ms=collector.latencies_ms,
        status_codes=dict(collector.status_codes),
        error_samples=collector.error_samples,
        budget_ms=scenario.budget_ms,
        wall_s=collector.wall_s,
        warnings=collector.warnings,
    )


def _environment(base_url: str, users: int) -> dict[str, Any]:
    """Окружение прогона — для отчёта и воспроизводимости."""
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "load_users": users,
        "runner": "asyncio+httpx (k6/locust недоступны: PyPI заблокирован)",
    }


def _print_table(results: list[ScenarioResult]) -> None:
    header = (
        "| Сценарий | RPS target | RPS факт | Запросы | Ошибки | "
        "p50, мс | p95, мс | p99, мс | Бюджет p95 | Вердикт |"
    )
    print()
    print(header)
    print("|---|---|---|---|---|---|---|---|---|---|")
    for result in results:
        print(
            f"| {result.name} | {result.rps_target:g} | "
            f"{result.achieved_rps:.1f} | {result.total} | "
            f"{result.errors} ({result.error_rate * 100:.2f}%) | "
            f"{result.p50:.1f} | {result.p95:.1f} | {result.p99:.1f} | "
            f"{result.budget_ms:g} мс | {result.verdict()} |"
        )
    print()


def _failures(results: list[ScenarioResult]) -> list[str]:
    failures: list[str] = []
    for result in results:
        if result.p95 > result.budget_ms:
            failures.append(
                f"{result.name}: p95 {result.p95:.1f} мс > {result.budget_ms:g} мс"
            )
        if result.error_rate > ERROR_RATE_LIMIT:
            failures.append(
                f"{result.name}: error rate {result.error_rate * 100:.2f}% > 1%"
            )
    return failures


async def main_async(args: argparse.Namespace) -> int:
    selected = (
        list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    )
    scenarios: list[Scenario] = []
    for name in selected:
        scenario = SCENARIOS[name]
        if args.rps is not None:
            scenario.rps = args.rps
        if args.concurrency is not None:
            scenario.concurrency = args.concurrency
        scenarios.append(scenario)

    user_count = max(1, args.users)
    uses_auth = any(scenario.needs_auth for scenario in scenarios)

    limits = httpx.Limits(max_connections=100, max_keepalive_connections=50)
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"), timeout=timeout, limits=limits
    ) as client:
        await _wait_for_health(client)
        print(f"[load] backend готов: {args.base_url}")

        users: list[UserSession] = []
        task_id = ""
        solution = ""
        if uses_auth:
            users = await _prepare_users(client, user_count)
            task_id, title, solution = await _pick_task_id(client, users[0])
            print(
                f"[load] пользователей: {len(users)}; задача: "
                f"{title} ({task_id})"
            )

        results: list[ScenarioResult] = []
        for scenario in scenarios:
            results.append(
                await _run_scenario(
                    client,
                    scenario,
                    users,
                    task_id,
                    solution,
                    args.duration,
                    args.warmup,
                )
            )

    _print_table(results)
    for result in results:
        if result.status_codes:
            print(
                f"[load] {result.name} status codes: "
                f"{json.dumps(result.status_codes, ensure_ascii=False)}"
            )
        if result.error_samples:
            print(f"[load] {result.name} error samples: {result.error_samples}")

    payload = {
        "environment": _environment(args.base_url, user_count),
        "scenarios": [result.as_dict() for result in results],
        "budgets": {
            "health_p95_ms": 300,
            "tasks_p95_ms": 300,
            "submit_p95_ms": 2000,
            "error_rate": ERROR_RATE_LIMIT,
        },
        "verdict": "PASS" if not _failures(results) else "FAIL",
    }
    if args.json_out:
        output_path = Path(args.json_out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[load] JSON сохранён: {output_path}")

    failures = _failures(results)
    if failures:
        print("[load] ПРОВАЛ БЮДЖЕТА:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("[load] Все бюджеты соблюдены.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Нагрузочный тест AI Teacher API (asyncio+httpx). "
            "Exit code 1 при p95 > бюджета или error rate > 1%."
        )
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"базовый URL backend (по умолчанию {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--scenario",
        choices=[*SCENARIOS, "all"],
        default="all",
        help="сценарий: health (50 RPS), tasks (20 RPS), submit (5 RPS) или all",
    )
    parser.add_argument(
        "--rps",
        type=float,
        default=None,
        help="переопределить целевой RPS для выбранных сценариев",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=25.0,
        help="длительность измерения на сценарий, секунды (по умолчанию 25)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="переопределить число одновременных запросов",
    )
    parser.add_argument(
        "--warmup",
        type=float,
        default=1.0,
        help="прогрев перед измерением, секунды (по умолчанию 1)",
    )
    parser.add_argument(
        "--users",
        type=int,
        default=3,
        help="число нагрузочных пользователей для авторизованных сценариев",
    )
    parser.add_argument(
        "--json-out",
        default=None,
        help="путь к JSON-файлу с результатами",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.duration <= 0:
        print("[load] --duration должен быть > 0", file=sys.stderr)
        return 2
    try:
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("[load] прервано пользователем", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
