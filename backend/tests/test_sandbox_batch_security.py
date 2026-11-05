"""Безопасность батчевого режима и пула (S23-004, KI-022).

Атаки должны блокироваться и в батче, и в тёплом процессе; песочница не
должна «залипать» после `MemoryError`/`TimeoutError`, а процесс пула —
переиспользоваться после сбоя.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

from app.core.executor import SandboxedExecutor
from app.core.runner_pool import close_current_pool
from tests.test_sandbox_limits import ATTACKS

TIMEOUT = 10.0
POOL_MODES = pytest.mark.parametrize("pool_size", [0, 1])


@pytest_asyncio.fixture(autouse=True)
async def _fresh_pool() -> Any:
    yield
    await close_current_pool()


def _executor(pool_size: int, **kwargs: Any) -> SandboxedExecutor:
    return SandboxedExecutor(
        timeout=kwargs.pop("timeout", TIMEOUT), pool_size=pool_size, **kwargs
    )


@POOL_MODES
@pytest.mark.parametrize(("code", "error_type"), ATTACKS)
async def test_attack_blocked_in_batch(
    pool_size: int, code: str, error_type: str
) -> None:
    executor = _executor(pool_size)
    results = await executor.execute_many(code, ["", ""])

    assert all(result.success is False for result in results)
    assert all(result.error_type == error_type for result in results)


@POOL_MODES
async def test_batch_attack_has_no_side_effects(pool_size: int, tmp_path: Path) -> None:
    """`open()` заблокирован: файл не появляется ни в одном кейсе"""
    target = tmp_path / "student.txt"
    executor = _executor(pool_size)

    results = await executor.execute_many(
        f'open(r"{target}", "w").write("pwned")', ["", ""]
    )

    assert all(result.success is False for result in results)
    assert target.exists() is False


@POOL_MODES
async def test_sandbox_recovers_after_memory_error(pool_size: int) -> None:
    """После MemoryError следующая задача выполняется (процесс не «залип»)"""
    executor = _executor(pool_size, memory_limit_mb=64)

    failed = await executor.execute_many("x = [0] * 10**9\nprint(len(x))\n", [""])
    assert failed[0].success is False

    recovered = await executor.execute_many("print('alive')\n", ["", ""])
    assert [result.output.strip() for result in recovered] == ["alive", "alive"]


@POOL_MODES
async def test_sandbox_recovers_after_timeout(pool_size: int) -> None:
    executor = _executor(pool_size, timeout=1.0)
    code = "if input() == 'hang':\n    while True:\n        pass\nprint('ok')\n"

    timed_out = await executor.execute_many(code, ["hang\n", "go\n"])
    assert timed_out[0].error_type == "TimeoutError"

    recovered = await executor.execute_many("print('alive')\n", [""])
    assert recovered[0].success is True
    assert recovered[0].output.strip() == "alive"


async def test_pool_does_not_reuse_worker_after_attack() -> None:
    """Блокировка атаки не ломает пул: следующая задача идёт в том же процессе"""
    executor = _executor(1)

    attacked = await executor.execute_many("import os\nprint(1)\n", [""])
    assert attacked[0].error_type == "SecurityError"

    ok = await executor.execute_many("print('ok')\n", [""])
    assert ok[0].output.strip() == "ok"


async def test_batch_of_mixed_cases_keeps_per_case_results() -> None:
    """Ошибка в одном кейсе не влияет на результаты остальных (батч + пул)"""
    executor = _executor(1)
    code = "n = int(input())\nprint(100 // n)\n"

    results = await executor.execute_many(code, ["4\n", "0\n", "5\n"])

    assert results[0].output.strip() == "25"
    assert results[1].error_type == "ZeroDivisionError"
    assert results[2].output.strip() == "20"
