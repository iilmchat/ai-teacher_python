"""Тесты батчевого раннера песочницы (S23-001, KI-022).

Один дочерний интерпретатор выполняет все кейсы задачи; проверяем
изоляцию между кейсами, таймаут на кейс, ошибки, лимиты и fallback.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from app.core.executor import SandboxedExecutor
from app.core.test_runner import run_test_cases

TIMEOUT = 10.0


def _executor(**kwargs: Any) -> SandboxedExecutor:
    """Одноразовый батчевый путь (пул проверяется в test_runner_pool)."""
    kwargs.setdefault("pool_size", 0)
    return SandboxedExecutor(**kwargs)


async def test_batch_executes_all_cases_in_one_process() -> None:
    executor = _executor(timeout=TIMEOUT, max_concurrency=2)
    code = "a = int(input())\nprint(a * 2)\n"

    results = await executor.execute_many(code, ["2\n", "3\n", "10\n"])

    assert [result.output.strip() for result in results] == ["4", "6", "20"]
    assert all(result.success for result in results)


async def test_batch_isolates_variables_between_cases() -> None:
    """Кейсы не видят переменные друг друга (свежие globals на кейс)"""
    executor = _executor(timeout=TIMEOUT, max_concurrency=2)
    code = (
        "try:\n"
        "    leaked\n"
        "except NameError:\n"
        "    print('fresh')\n"
        "else:\n"
        "    print('leaked')\n"
        "leaked = 1\n"
    )

    results = await executor.execute_many(code, ["", "", ""])

    assert [result.output.strip() for result in results] == ["fresh", "fresh", "fresh"]


async def test_batch_error_in_one_case_does_not_break_others() -> None:
    executor = _executor(timeout=TIMEOUT, max_concurrency=2)
    code = "a = int(input())\nprint(10 // a)\n"

    results = await executor.execute_many(code, ["0\n", "2\n"])

    assert results[0].success is False
    assert results[0].error_type == "ZeroDivisionError"
    assert results[1].success is True
    assert results[1].output.strip() == "5"


async def test_batch_timeout_per_case() -> None:
    """Зависший кейс убивает процесс; остальные помечаются SandboxError"""
    executor = _executor(timeout=1.0, max_concurrency=2)
    code = "if input() == 'hang':\n    while True:\n        pass\nprint('ok')\n"

    results = await executor.execute_many(code, ["hang\n", "go\n"])

    assert len(results) == 2
    assert results[0].error_type == "TimeoutError"
    assert results[1].success is False
    assert results[1].error_type == "SandboxError"


async def test_batch_security_violation_is_reported_for_each_case() -> None:
    executor = _executor(timeout=TIMEOUT, max_concurrency=2)

    results = await executor.execute_many("import os\nprint(input())\n", ["1\n", "2\n"])

    assert all(result.success is False for result in results)
    assert all(result.error_type == "SecurityError" for result in results)
    assert all(result.violations for result in results)


async def test_batch_systemexit_does_not_kill_batch() -> None:
    """`raise SystemExit` (BaseException) не должен ронять весь батч"""
    executor = _executor(timeout=TIMEOUT, max_concurrency=2)
    code = "if input() == 'exit':\n    raise SystemExit(3)\nprint('alive')\n"

    results = await executor.execute_many(code, ["exit\n", "ok\n"])

    assert results[0].success is False
    assert results[0].error_type in {"SystemExit", "BaseException"}
    assert results[1].success is True
    assert results[1].output.strip() == "alive"


async def test_batch_truncates_output_per_case() -> None:
    executor = SandboxedExecutor(
        timeout=TIMEOUT, max_output_chars=50, max_concurrency=2
    )

    results = await executor.execute_many("print('x' * 500)\n", ["", ""])

    assert all(result.output_truncated for result in results)
    assert all(len(result.output) <= 120 for result in results)


async def test_batch_utf8_output() -> None:
    executor = _executor(timeout=TIMEOUT, max_concurrency=2)

    results = await executor.execute_many("print('привет, ученик')\n", [""])

    assert results[0].output.strip() == "привет, ученик"


async def test_batch_memory_limit_is_enforced() -> None:
    executor = _executor(timeout=TIMEOUT, memory_limit_mb=64, max_concurrency=2)

    results = await executor.execute_many("x = [0] * 10**9\nprint(len(x))\n", [""])

    assert results[0].success is False
    assert results[0].error_type in {"MemoryError", "SandboxError"}


async def test_execute_many_without_cases_returns_empty_list() -> None:
    executor = _executor(timeout=TIMEOUT)

    assert await executor.execute_many("print(1)", []) == []


async def test_execute_many_falls_back_when_subprocess_unavailable() -> None:
    """Нет поддержки subprocess в loop (или ОС) — последовательный fallback"""
    executor = _executor(timeout=TIMEOUT, max_concurrency=2)

    def _unsupported(*args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("subprocess не поддерживается")

    with patch.object(asyncio, "create_subprocess_exec", _unsupported):
        results = await executor.execute_many("print(input())\n", ["a\n", "b\n"])

    assert [result.output.strip() for result in results] == ["a", "b"]


async def test_run_test_cases_uses_batch_path() -> None:
    """`run_test_cases` идёт батчевым путём, а не по одному `execute`"""
    executor = _executor(timeout=TIMEOUT, max_concurrency=2)
    cases = [
        {"input": "2\n", "expected_output": "4"},
        {"input": "5\n", "expected_output": "10"},
        {"input": "-3\n", "expected_output": "-6"},
    ]

    def _forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("run_test_cases должен использовать execute_many")

    with patch.object(SandboxedExecutor, "execute", _forbidden):
        outcome = await run_test_cases(executor, "print(int(input()) * 2)\n", cases)

    assert outcome.passed is True
    assert outcome.passed_count == 3


async def test_run_test_cases_reports_per_case_results() -> None:
    executor = _executor(timeout=TIMEOUT, max_concurrency=2)
    cases = [
        {"input": "2\n", "expected_output": "4", "description": "ok"},
        {"input": "2\n", "expected_output": "5", "description": "wrong"},
    ]

    outcome = await run_test_cases(executor, "print(int(input()) * 2)\n", cases)

    assert outcome.passed is False
    assert outcome.passed_count == 1
    assert outcome.results[0].description == "ok"
    assert outcome.results[1].actual_output.strip() == "4"


@pytest.mark.parametrize("cases_count", [1, 5, 20])
async def test_batch_handles_max_case_counts(cases_count: int) -> None:
    executor = _executor(timeout=TIMEOUT, max_concurrency=2)
    cases = [
        {"input": f"{index}\n", "expected_output": str(index)}
        for index in range(cases_count)
    ]

    outcome = await run_test_cases(executor, "print(input().strip())\n", cases)

    assert outcome.passed is True
    assert outcome.total_count == cases_count
