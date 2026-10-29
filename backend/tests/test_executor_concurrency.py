"""
Тесты ограничения одновременных запусков песочницы (S13-003).

Семафор общий на процесс; при перегрузке API получает 503, а не копит
потоки без ограничения.
"""

import asyncio
import threading
import time
from collections.abc import Iterator

import pytest

from app.core.executor import (
    ExecutionResult,
    SandboxedExecutor,
    reset_executor_slots,
)
from app.errors import ServiceUnavailableError


@pytest.fixture(autouse=True)
def clear_slots() -> Iterator[None]:
    reset_executor_slots()
    yield
    reset_executor_slots()


async def test_busy_sandbox_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    """Если слот занят дольше queue_timeout — ServiceUnavailableError"""
    executor = SandboxedExecutor(timeout=5, max_concurrency=1, queue_timeout=0.1)
    release = threading.Event()

    def slow(code: str, stdin_text: str = "") -> ExecutionResult:
        release.wait(2)
        return ExecutionResult(success=True, output=code)

    monkeypatch.setattr(executor, "_execute_in_process", slow)

    first = asyncio.create_task(executor.execute("first"))
    await asyncio.sleep(0.05)
    try:
        with pytest.raises(ServiceUnavailableError) as exc_info:
            await executor.execute("second")
    finally:
        release.set()

    assert "перегружена" in exc_info.value.detail
    assert (await first).output == "first"


async def test_parallel_runs_respect_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """10 параллельных запусков при лимите 3 — без превышения лимита"""
    executor = SandboxedExecutor(
        timeout=5, max_concurrency=3, queue_timeout=5.0
    )
    active = 0
    peak = 0
    lock = threading.Lock()

    def fake(code: str, stdin_text: str = "") -> ExecutionResult:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.1)
        with lock:
            active -= 1
        return ExecutionResult(success=True, output=code)

    monkeypatch.setattr(executor, "_execute_in_process", fake)

    results = await asyncio.gather(
        *(executor.execute(f"code-{index}") for index in range(10))
    )

    assert len(results) == 10
    assert peak <= 3


async def test_slot_is_released_after_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ошибка выполнения не «съедает» слот"""
    executor = SandboxedExecutor(timeout=1, max_concurrency=1, queue_timeout=0.1)

    def failing(code: str, stdin_text: str = "") -> ExecutionResult:
        raise RuntimeError("boom")

    monkeypatch.setattr(executor, "_execute_in_process", failing)

    with pytest.raises(RuntimeError):
        await executor.execute("bad")

    monkeypatch.setattr(
        executor,
        "_execute_in_process",
        lambda code, stdin_text="": ExecutionResult(success=True, output="ok"),
    )
    assert (await executor.execute("good")).output == "ok"
