"""
Тесты лимита памяти песочницы (S13-001 — POSIX, S13-002 — Windows).

Каждый тест запускает дочерний интерпретатор и проверяет, что превышение
лимита даёт `MemoryError`, а не убивает процесс API/тестов.
"""

import sys

import pytest

from app.config import settings
from app.core.executor import SandboxedExecutor

pytestmark = pytest.mark.slow

#: 10**9 нулей — 8 ГБ, заведомо больше любого лимита
HUGE_ALLOCATION = "x = [0] * 10**9"


def test_default_memory_limit_comes_from_settings() -> None:
    assert SandboxedExecutor(timeout=1).memory_limit_mb == settings.executor_memory_limit


async def test_normal_code_fits_under_limit() -> None:
    """Обычный код не страдает от лимита памяти"""
    executor = SandboxedExecutor(timeout=10, memory_limit_mb=128)

    result = await executor.execute("print(sum(range(10)))")

    assert result.success is True
    assert result.output.strip() == "45"
    assert result.memory_limit_enforced is True


async def test_executor_truncates_huge_output() -> None:
    """Вывод 1 МБ обрезается, ответ не «раздувается» (S13-005)"""
    executor = SandboxedExecutor(timeout=10, max_output_chars=1000)

    result = await executor.execute("print('x' * 1_000_000)")

    assert result.success is True
    assert result.output_truncated is True
    assert len(result.output) <= 1000
    assert "вывод обрезан" in result.output


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Object")
async def test_windows_memory_limit_enforced() -> None:
    """Windows: Job Object с JOB_OBJECT_LIMIT_PROCESS_MEMORY"""
    executor = SandboxedExecutor(timeout=15, memory_limit_mb=128)

    result = await executor.execute(HUGE_ALLOCATION)

    assert result.success is False
    assert result.memory_limit_enforced is True
    assert result.error_type == "MemoryError"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX RLIMIT_AS")
async def test_posix_memory_limit_enforced() -> None:
    """Linux/macOS: resource.setrlimit(RLIMIT_AS)"""
    executor = SandboxedExecutor(timeout=15, memory_limit_mb=128)

    result = await executor.execute(HUGE_ALLOCATION)

    assert result.success is False
    assert result.memory_limit_enforced is True
    assert result.error_type == "MemoryError"
