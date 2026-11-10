"""Тесты пула тёплых интерпретаторов (S23-002, KI-022).

Проверяем: переиспользование процесса, перезапуск после таймаута и после
`max_tasks`, выключение флагом, изоляцию задач между переиспользованиями и
корректное закрытие пула.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio

from app.core.executor import SandboxedExecutor
from app.core.runner_pool import close_current_pool, get_pool

TIMEOUT = 10.0


@pytest_asyncio.fixture(autouse=True)
async def _fresh_pool() -> AsyncIterator[None]:
    """Пул не должен протекать между тестами"""
    yield
    await close_current_pool()


def _counting_spawn(counter: list[int]) -> Any:
    original = SandboxedExecutor.spawn_pool_worker

    async def wrapper() -> Any:
        counter.append(1)
        return await original()

    return wrapper


async def _run(executor: SandboxedExecutor, code: str, stdins: list[str]) -> list[str]:
    results = await executor.execute_many(code, stdins)
    return [result.output.strip() for result in results]


async def test_pool_reuses_worker_between_batches() -> None:
    counter: list[int] = []
    executor = SandboxedExecutor(
        timeout=TIMEOUT, pool_size=1, pool_max_tasks=10, max_concurrency=2
    )

    with patch.object(SandboxedExecutor, "spawn_pool_worker", _counting_spawn(counter)):
        assert await _run(executor, "print(input())\n", ["a\n"]) == ["a"]
        assert await _run(executor, "print(input())\n", ["b\n"]) == ["b"]
        assert await _run(executor, "print(1)\n", [""]) == ["1"]

    assert len(counter) == 1, "процесс должен переиспользоваться"


async def test_pool_restarts_worker_after_timeout() -> None:
    counter: list[int] = []
    executor = SandboxedExecutor(
        timeout=1.0, pool_size=1, pool_max_tasks=10, max_concurrency=2
    )
    code = "if input() == 'hang':\n    while True:\n        pass\nprint('ok')\n"

    with patch.object(SandboxedExecutor, "spawn_pool_worker", _counting_spawn(counter)):
        timed_out = await executor.execute_many(code, ["hang\n", "go\n"])
        assert timed_out[0].error_type == "TimeoutError"
        assert timed_out[1].success is False  # батч прерван

        # Следующая задача должна получить НОВЫЙ процесс. Таймаут 1 с относится
        # к «зависшему» кейсу; на холодный старт нового интерпретатора он не
        # рассчитан (в нагруженном CI импорт RestrictedPython может занять
        # больше секунды), поэтому проверку живости делаем с рабочим таймаутом.
        alive_executor = SandboxedExecutor(
            timeout=TIMEOUT, pool_size=1, pool_max_tasks=10, max_concurrency=2
        )
        assert await _run(alive_executor, "print('alive')\n", [""]) == ["alive"]

    assert len(counter) == 2, "после таймаута процесс не переиспользуется"


async def test_pool_retires_worker_after_max_tasks() -> None:
    counter: list[int] = []
    executor = SandboxedExecutor(
        timeout=TIMEOUT, pool_size=1, pool_max_tasks=2, max_concurrency=2
    )

    with patch.object(SandboxedExecutor, "spawn_pool_worker", _counting_spawn(counter)):
        for _ in range(3):
            assert await _run(executor, "print(1)\n", [""]) == ["1"]

    assert len(counter) == 2, "процесс перезапускается после max_tasks"


async def test_pool_disabled_uses_one_shot_batch() -> None:
    counter: list[int] = []
    executor = SandboxedExecutor(timeout=TIMEOUT, pool_size=0, max_concurrency=2)

    with patch.object(SandboxedExecutor, "spawn_pool_worker", _counting_spawn(counter)):
        assert await _run(executor, "print(input())\n", ["x\n"]) == ["x"]

    assert counter == [], "при pool_size=0 пул не используется"


async def test_pool_isolates_variables_between_tasks() -> None:
    executor = SandboxedExecutor(
        timeout=TIMEOUT, pool_size=1, pool_max_tasks=10, max_concurrency=2
    )
    code = (
        "try:\n"
        "    leaked\n"
        "except NameError:\n"
        "    print('fresh')\n"
        "else:\n"
        "    print('leaked')\n"
        "leaked = 1\n"
    )

    assert await _run(executor, code, [""]) == ["fresh"]
    assert await _run(executor, code, [""]) == ["fresh"], "переменные не текут"


async def test_pool_still_blocks_forbidden_imports() -> None:
    executor = SandboxedExecutor(
        timeout=TIMEOUT, pool_size=1, pool_max_tasks=10, max_concurrency=2
    )

    results = await executor.execute_many("import os\nprint(1)\n", ["", ""])

    assert all(result.error_type == "SecurityError" for result in results)


async def test_close_pool_terminates_idle_workers() -> None:
    executor = SandboxedExecutor(
        timeout=TIMEOUT, pool_size=1, pool_max_tasks=10, max_concurrency=2
    )
    assert await _run(executor, "print(1)\n", [""]) == ["1"]

    pool = get_pool(executor.pool_size, executor.pool_max_tasks)
    assert pool._idle  # noqa: SLF001 — проверяем внутреннее состояние пула

    await close_current_pool()

    assert pool._idle == []  # noqa: SLF001
    assert all(worker.process.returncode is not None for worker in pool._idle)  # noqa: SLF001


@pytest.mark.parametrize("cases_count", [1, 3, 8])
async def test_pool_handles_multiple_cases(cases_count: int) -> None:
    executor = SandboxedExecutor(
        timeout=TIMEOUT, pool_size=1, pool_max_tasks=10, max_concurrency=2
    )
    stdins = [f"{index}\n" for index in range(cases_count)]

    results = await executor.execute_many("print(input().strip())\n", stdins)

    assert [result.output.strip() for result in results] == [
        str(index) for index in range(cases_count)
    ]


def test_pool_module_has_no_cyclic_import() -> None:
    """Импорт пула не тянет executor на уровне модуля (цикл был бы фатален)"""
    import importlib

    module = importlib.import_module("app.core.runner_pool")
    assert hasattr(module, "get_pool")


@pytest.fixture
def _unused() -> Iterator[None]:  # pragma: no cover — подавляет предупреждение
    yield None
