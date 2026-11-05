"""Тесты контейнерного раннера (S24-001/S24-002).

Часть без Docker проверяет команду изоляции, протокол и fallback; реальный
контейнер — в `test_container_isolation.py` (skip без Docker/образа).
"""

from __future__ import annotations

import shutil
from typing import Any
from unittest.mock import patch

from app.core.container_sandbox import (
    DEFAULT_IMAGE,
    ContainerSandbox,
    container_available,
    metrics,
    reset_availability_cache,
)
from app.core.executor import SandboxedExecutor

FAKE_DOCKER = "C:\\fake\\docker.exe"


def test_build_command_contains_all_isolation_flags() -> None:
    sandbox = ContainerSandbox(image="img:test", memory_limit_mb=96)

    command = sandbox.build_command()
    joined = " ".join(command)

    assert "--rm" in command
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command
    assert command[command.index("--cap-drop") + 1] == "ALL"
    assert command[command.index("--security-opt") + 1] == "no-new-privileges"
    assert command[command.index("--user") + 1] == "65534:65534"
    assert command[command.index("--tmpfs") + 1].startswith("/tmp:")
    assert command[command.index("--memory") + 1] == "96m"
    assert command[command.index("--memory-swap") + 1] == "96m"
    assert command[command.index("--pids-limit") + 1] == "64"
    assert command[command.index("--pull") + 1] == "never"
    assert command[-1] == "img:test"
    assert "img:test" in joined


def test_payload_is_single_json_line() -> None:
    sandbox = ContainerSandbox(image="img:test")

    raw = sandbox.build_payload("print(1)", ["a\n", "b\n"])

    assert raw.endswith(b"\n")
    assert raw.count(b"\n") == 1
    assert b'"cases"' in raw


def test_result_from_payload_parses_fields() -> None:
    result = ContainerSandbox._result_from_payload(
        {
            "success": True,
            "output": "5\n",
            "error": None,
            "error_type": None,
            "execution_time": 0.01,
            "violations": ["v1"],
            "memory_limit_enforced": True,
            "output_truncated": False,
        },
        0.5,
    )

    assert result.success is True
    assert result.output == "5\n"
    assert result.violations == ["v1"]
    assert result.memory_limit_enforced is True
    assert result.execution_time == 0.01


def test_metrics_snapshot_counts_runs_and_fallbacks() -> None:
    metrics.runs = 0
    metrics.errors = 0
    metrics.timeouts = 0
    metrics.fallbacks = 0
    metrics.start_ms_total = 0.0

    metrics.record_run(120.0, 128)
    metrics.record_run(180.0, 128)
    metrics.record_error()
    metrics.record_timeout()
    metrics.record_fallback()

    snapshot = metrics.snapshot()
    assert snapshot["runs"] == 2
    assert snapshot["errors"] == 1
    assert snapshot["timeouts"] == 1
    assert snapshot["fallbacks"] == 1
    assert snapshot["start_ms_avg"] == 150.0
    assert snapshot["memory_limit_mb"] == 128


def test_container_unavailable_without_docker() -> None:
    reset_availability_cache()
    with patch.object(shutil, "which", return_value=None):
        assert container_available(DEFAULT_IMAGE) is False
        assert ContainerSandbox(image=DEFAULT_IMAGE).build_command()[0] == "docker"


async def test_executor_falls_back_to_native_without_docker() -> None:
    """Нет Docker → контейнерный режим откатывается на нативный, submit работает"""
    reset_availability_cache()
    metrics.fallbacks = 0

    with patch.object(shutil, "which", return_value=None):
        executor = SandboxedExecutor(mode="container", timeout=10, pool_size=0)
        results = await executor.execute_many("print(input().strip() * 2)", ["x\n"])

    assert results[0].success is True
    assert results[0].output.strip() == "xx"
    assert metrics.fallbacks >= 1


async def test_executor_falls_back_when_image_missing() -> None:
    """Docker есть, но образа нет (`--pull never`) → нативный режим"""
    reset_availability_cache()

    executor = SandboxedExecutor(
        mode="container", image="ai-teacher-missing-image:none", timeout=10, pool_size=0
    )
    results = await executor.execute_many("print(2 + 2)", [""])

    assert results[0].success is True
    assert results[0].output.strip() == "4"


async def test_native_mode_does_not_touch_docker() -> None:
    executor = SandboxedExecutor(mode="native", timeout=10, pool_size=0)

    with patch.object(ContainerSandbox, "run_batch", side_effect=AssertionError("docker")):
        results = await executor.execute_many("print(7)", [""])

    assert results[0].output.strip() == "7"


def test_mode_and_image_from_constructor() -> None:
    executor = SandboxedExecutor(mode="CONTAINER ", image="custom:1")
    assert executor.mode == "container"
    assert executor.image == "custom:1"


def _any(value: Any) -> Any:  # pragma: no cover — helper для читаемости
    return value
