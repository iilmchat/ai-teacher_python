"""Контейнерный раннер песочницы (S24-001..004).

Образ `ai-teacher-sandbox-runner` (см. `backend/sandbox_runner/`) содержит только
`RestrictedPython` и чистое ядро песочницы. Запуск — на каждый батч:

    docker run --rm -i --network none --read-only --cap-drop ALL \
        --security-opt no-new-privileges --user 65534:65534 \
        --tmpfs /tmp:rw,noexec,nosuid,size=64m \
        --memory <mb>m --memory-swap <mb>m --pids-limit 64 \
        --pull never ai-teacher-sandbox-runner:latest

Протокол — тот же, что у нативного батча: одна JSON-строка запроса в stdin,
по строке результата на кейс в stdout, затем `{"done": true}`.

Если Docker недоступен, образ не собран или контейнер не выдал ни строки,
`run_batch` возвращает `None` — вызывающий код откатывается на нативный режим
(с предупреждением в логе), а не ломает submit.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field

import structlog

from app.core.sandbox_runtime import ExecutionResult

logger = structlog.get_logger(__name__)

DEFAULT_IMAGE = "ai-teacher-sandbox-runner:latest"
CONTAINER_USER = "65534:65534"


@dataclass(slots=True)
class ContainerMetrics:
    """Счётчики контейнерного режима (S24-004; в /metrics — спринт 25)"""

    runs: int = 0
    errors: int = 0
    timeouts: int = 0
    fallbacks: int = 0
    start_ms_total: float = 0.0
    start_ms_last: float = 0.0
    memory_limit_mb: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_run(self, start_ms: float, memory_limit_mb: int) -> None:
        with self._lock:
            self.runs += 1
            self.start_ms_last = start_ms
            self.start_ms_total += start_ms
            self.memory_limit_mb = memory_limit_mb

    def record_error(self) -> None:
        with self._lock:
            self.errors += 1

    def record_timeout(self) -> None:
        with self._lock:
            self.timeouts += 1

    def record_fallback(self) -> None:
        with self._lock:
            self.fallbacks += 1

    @property
    def start_ms_avg(self) -> float:
        with self._lock:
            return self.start_ms_total / self.runs if self.runs else 0.0

    def snapshot(self) -> dict[str, float | int]:
        with self._lock:
            return {
                "runs": self.runs,
                "errors": self.errors,
                "timeouts": self.timeouts,
                "fallbacks": self.fallbacks,
                "start_ms_avg": round(self.start_ms_total / self.runs, 1)
                if self.runs
                else 0.0,
                "start_ms_last": round(self.start_ms_last, 1),
                "memory_limit_mb": self.memory_limit_mb,
            }


#: Глобальные метрики контейнерного режима (сбрасываются в тестах)
metrics = ContainerMetrics()


def docker_path() -> str | None:
    """Путь к docker CLI или None, если его нет.

    На Windows `shutil.which("docker")` может вернуть шим Docker Desktop без
    `.exe` — CreateProcess на нём падает с WinError 193, поэтому ищем именно
    исполняемый файл.
    """
    if sys.platform == "win32":
        for name in ("docker.exe", "docker.cmd", "docker.bat", "docker"):
            found = shutil.which(name)
            if found:
                return found
        return None
    return shutil.which("docker")


_availability_cache: tuple[str, bool] | None = None
_availability_lock = threading.Lock()
_warned_unavailable = False


def container_available(image: str) -> bool:
    """Есть ли docker и собран ли образ (кешируется на процесс)"""
    global _availability_cache
    if docker_path() is None:
        return False
    with _availability_lock:
        if _availability_cache is not None and _availability_cache[0] == image:
            return _availability_cache[1]
        try:
            completed = subprocess.run(  # noqa: S603 — фиксированная команда
                [docker_path() or "docker", "image", "inspect", image],
                capture_output=True,
                timeout=15,
                check=False,
            )
            available = completed.returncode == 0
        except (OSError, subprocess.SubprocessError):
            available = False
        _availability_cache = (image, available)
        return available


def reset_availability_cache() -> None:
    """Сбросить кеш (тесты)"""
    global _availability_cache
    with _availability_lock:
        _availability_cache = None


class ContainerSandbox:
    """Запуск батча тест-кейсов в одноразовом контейнере"""

    def __init__(
        self,
        *,
        image: str = DEFAULT_IMAGE,
        timeout: float = 5.0,
        memory_limit_mb: int = 128,
        max_output_chars: int = 100_000,
    ) -> None:
        self.image = image
        self.timeout = timeout
        self.memory_limit_mb = max(1, memory_limit_mb)
        self.max_output_chars = max_output_chars

    def build_command(self) -> list[str]:
        """Команда `docker run` со всеми флагами изоляции (S24-001)"""
        docker = docker_path() or "docker"
        return [
            docker, "run", "--rm", "-i",
            "--network", "none",
            "--read-only",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--user", CONTAINER_USER,
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "--memory", f"{self.memory_limit_mb}m",
            "--memory-swap", f"{self.memory_limit_mb}m",
            "--pids-limit", "64",
            "--pull", "never",
            self.image,
        ]

    def build_payload(self, code: str, stdins: list[str]) -> bytes:
        payload = json.dumps(
            {
                "code": code,
                "cases": list(stdins),
                "memory_limit_mb": self.memory_limit_mb,
                "max_output_chars": self.max_output_chars,
            },
            ensure_ascii=False,
        )
        return (payload + "\n").encode("utf-8")

    @staticmethod
    def _result_from_payload(raw: dict[str, object], elapsed: float) -> ExecutionResult:
        error = raw.get("error")
        error_type = raw.get("error_type")
        violations = raw.get("violations")
        try:
            execution_time = float(raw.get("execution_time") or elapsed)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            execution_time = elapsed
        return ExecutionResult(
            success=bool(raw.get("success")),
            output=str(raw.get("output", "")),
            error=error if isinstance(error, str) else None,
            execution_time=execution_time,
            error_type=error_type if isinstance(error_type, str) else None,
            violations=[str(item) for item in violations]
            if isinstance(violations, list)
            else [],
            memory_limit_enforced=bool(raw.get("memory_limit_enforced")),
            output_truncated=bool(raw.get("output_truncated")),
        )

    async def run_batch(
        self, code: str, stdins: list[str]
    ) -> list[ExecutionResult] | None:
        """Выполнить батч в контейнере; `None` — откат на нативный режим"""
        if not stdins:
            return None
        if not container_available(self.image):
            metrics.record_fallback()
            global _warned_unavailable
            if not _warned_unavailable:
                _warned_unavailable = True
                logger.warning(
                    "sandbox_container_unavailable",
                    image=self.image,
                    fallback="native",
                )
            return None

        started = time.perf_counter()
        try:
            process = await asyncio.create_subprocess_exec(
                *self.build_command(),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (OSError, NotImplementedError) as exc:
            logger.warning("sandbox_container_unavailable", error=str(exc))
            metrics.record_fallback()
            return None

        assert process.stdin is not None
        assert process.stdout is not None

        results: list[ExecutionResult | None] = [None] * len(stdins)
        try:
            process.stdin.write(self.build_payload(code, stdins))
            await process.stdin.drain()
            process.stdin.close()

            for index in range(len(stdins)):
                try:
                    line = await asyncio.wait_for(
                        process.stdout.readline(), timeout=self.timeout
                    )
                except TimeoutError:
                    metrics.record_timeout()
                    results[index] = ExecutionResult(
                        success=False,
                        error=(
                            "Превышен лимит времени выполнения "
                            f"({self.timeout:.0f} с)"
                        ),
                        error_type="TimeoutError",
                        execution_time=time.perf_counter() - started,
                    )
                    break
                if not line:
                    break
                try:
                    raw = json.loads(line.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    break
                if not isinstance(raw, dict):
                    break
                results[index] = self._result_from_payload(
                    raw, time.perf_counter() - started
                )

            if all(result is not None for result in results):
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(process.stdout.readline(), timeout=self.timeout)
        finally:
            stderr_text = ""
            if process.returncode is None:
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    process.kill()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(process.wait(), timeout=10)
            if process.stderr is not None:
                with contextlib.suppress(Exception):
                    stderr_text = (
                        await asyncio.wait_for(process.stderr.read(), timeout=5)
                    ).decode("utf-8", errors="replace").strip()

        if all(result is None for result in results):
            # Контейнер не запустился/не ответил: это не ошибка кода ученика —
            # откатываемся на нативный режим.
            metrics.record_fallback()
            logger.warning(
                "sandbox_container_failed",
                image=self.image,
                stderr=stderr_text[-500:],
            )
            return None

        elapsed_ms = (time.perf_counter() - started) * 1000
        metrics.record_run(elapsed_ms, self.memory_limit_mb)
        if any(result is None for result in results):
            metrics.record_error()
            fallback_error = f"Сбой контейнера: {stderr_text[-300:] or 'нет ответа'}"
            for index, result in enumerate(results):
                if result is None:
                    results[index] = ExecutionResult(
                        success=False,
                        error=fallback_error,
                        error_type="SandboxError",
                        execution_time=time.perf_counter() - started,
                    )
        return [result for result in results if result is not None]
