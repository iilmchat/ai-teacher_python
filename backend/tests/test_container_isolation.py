"""Тесты изоляции контейнерного раннера (S24-003).

Требуют Docker и собранного образа `ai-teacher-sandbox-runner:latest`:

    pwsh scripts/ci/build-sandbox-image.ps1

Без Docker/образа тесты пропускаются (в CI `test`-job контейнера нет — образ
проверяется в `docker`-job через self-check).
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from app.core.container_sandbox import (
    DEFAULT_IMAGE,
    ContainerSandbox,
    container_available,
    reset_availability_cache,
)
from app.core.executor import SandboxedExecutor
from tests.test_sandbox_limits import ATTACKS

pytestmark = pytest.mark.skipif(
    shutil.which("docker") is None or not container_available(DEFAULT_IMAGE),
    reason="нужен Docker и образ ai-teacher-sandbox-runner (S24)",
)


def _self_check() -> dict[str, object]:
    sandbox = ContainerSandbox(image=DEFAULT_IMAGE)
    completed = subprocess.run(  # noqa: S603 — фиксированная команда
        [*sandbox.build_command(), "--self-check"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-800:]
    return json.loads(completed.stdout.strip().splitlines()[-1])


def _executor(**kwargs: object) -> SandboxedExecutor:
    defaults: dict[str, object] = {
        "mode": "container",
        "timeout": 20,
        "pool_size": 0,
    }
    defaults.update(kwargs)
    return SandboxedExecutor(**defaults)  # type: ignore[arg-type]


async def test_container_isolation_self_check() -> None:
    """read-only rootfs, non-root, нет сети и capabilities"""
    report = _self_check()

    assert report["uid"] == 65534
    assert report["read_only_rootfs"] is True
    assert report["tmp_writable"] is True
    assert report["network_blocked"] is True
    assert report["capabilities_zero"] is True


async def test_container_executes_batch() -> None:
    executor = _executor()

    results = await executor.execute_many("print(input().strip() * 2)", ["a\n", "b\n"])

    assert [result.output.strip() for result in results] == ["aa", "bb"]


async def test_container_isolates_cases() -> None:
    executor = _executor()
    code = (
        "try:\n"
        "    leaked\n"
        "except NameError:\n"
        "    print('fresh')\n"
        "else:\n"
        "    print('leaked')\n"
        "leaked = 1\n"
    )

    results = await executor.execute_many(code, ["", ""])

    assert [result.output.strip() for result in results] == ["fresh", "fresh"]


@pytest.mark.parametrize(("code", "error_type"), ATTACKS)
async def test_attacks_blocked_in_container(code: str, error_type: str) -> None:
    executor = _executor()

    results = await executor.execute_many(code, [""])

    assert results[0].success is False
    assert results[0].error_type == error_type


async def test_container_memory_limit() -> None:
    executor = _executor(memory_limit_mb=64)

    results = await executor.execute_many("x = [0] * 10**9\nprint(len(x))", [""])

    assert results[0].success is False


async def test_container_timeout_and_recovery() -> None:
    executor = _executor(timeout=2)
    code = "if input() == 'hang':\n    while True:\n        pass\nprint('ok')\n"

    timed_out = await executor.execute_many(code, ["hang\n", "go\n"])
    assert timed_out[0].error_type == "TimeoutError"

    recovered = await executor.execute_many("print('alive')", [""])
    assert recovered[0].success is True
    assert recovered[0].output.strip() == "alive"


async def test_container_output_truncated() -> None:
    executor = _executor(max_output_chars=50)

    results = await executor.execute_many("print('x' * 500)", [""])

    assert results[0].output_truncated is True


def test_image_available_for_tests() -> None:
    reset_availability_cache()
    assert container_available(DEFAULT_IMAGE) is True
