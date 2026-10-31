"""
Безопасное выполнение Python-кода ученика (S6-001, S6-002, S6-003, S24).

Защита в несколько слоёв:

1. Статический анализ AST — отклоняет запрещённые импорты, `eval`/`exec`/`open`,
   dunder-атрибуты (`find_violations`, `sandbox_runtime`).
2. `compile_restricted` (RestrictedPython) — ограниченный синтаксис.
3. Ограниченные builtins + guard'ы доступа к атрибутам и записи.
4. Собственный `__import__` с белым списком модулей.
5. Выполнение в отдельном процессе интерпретатора Python (нативный режим) или
   в отдельном **контейнере** (S24, `EXECUTOR_MODE=container`): сеть выключена,
   rootfs read-only, все capabilities сброшены, non-root, tmpfs для `/tmp`.
6. Лимит памяти ставится в дочернем процессе/контейнере: `RLIMIT_AS`, Job
   Object или `--memory` контейнера; вывод обрезается по лимиту (S13-005),
   число одновременных запусков ограничено (S13-003).

Почему subprocess, а не multiprocessing: на Windows spawn перезапускает
`__main__`, что конфликтует с uvicorn («Safe importing of main module»).
Отдельный интерпретатор/контейнер изолирован полностью и не зависит от `__main__`.

Чистое ядро песочницы (выполнение RestrictedPython без зависимостей приложения)
живёт в `app.core.sandbox_runtime` — его же копируют в образ контейнера.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.container_sandbox import ContainerSandbox
from app.core.metrics import sandbox_observed
from app.core.runner_pool import PooledWorker, get_pool
from app.core.sandbox_runtime import (
    ALLOWED_MODULES,
    FORBIDDEN_CALLS,
    FORBIDDEN_MODULES,
    ExecutionResult,
    find_violations,
)
from app.core.sandbox_runtime import run_restricted as _run_restricted
from app.errors import ServiceUnavailableError

__all__ = [
    "ALLOWED_MODULES",
    "BACKEND_DIR",
    "ExecutionResult",
    "FORBIDDEN_CALLS",
    "FORBIDDEN_MODULES",
    "SandboxedExecutor",
    "_run_restricted",
    "find_violations",
    "reset_executor_slots",
]

#: Каталог backend — нужен, чтобы дочерний интерпретатор импортировал `app`
BACKEND_DIR = Path(__file__).resolve().parents[2]

#: Код раннера: читает JSON {code, stdin, memory_limit_mb, max_output_chars}
#: из stdin, пишет JSON-результат в stdout
_RUNNER = (
    "import json, sys\n"
    "from app.core.executor import _run_restricted\n"
    "payload = json.loads(sys.stdin.read())\n"
    "result = _run_restricted(\n"
    "    payload['code'], payload.get('stdin', ''),\n"
    "    memory_limit_mb=payload.get('memory_limit_mb'),\n"
    "    max_output_chars=payload.get('max_output_chars'),\n"
    "    apply_limits=True,\n"
    ")\n"
    "sys.stdout.write(json.dumps(result, ensure_ascii=False))\n"
)

#: Батчевый раннер (S23-001): один интерпретатор на все кейсы задачи.
#: Читает одну JSON-строку {code, cases: [stdin...], memory_limit_mb,
#: max_output_chars} и на каждый кейс пишет отдельную JSON-строку с `index`.
#: Лимит памяти ставится один раз (первый кейс): RLIMIT_AS нельзя ослаблять
#: вверх, а Job Object нельзя навесить дважды. Прогресс построчный, чтобы
#: родитель мог уложить таймаут на каждый кейс и не ждать весь батч.
_BATCH_RUNNER = (
    "import json, sys\n"
    "from app.core.executor import _run_restricted\n"
    "payload = json.loads(sys.stdin.readline())\n"
    "cases = payload.get('cases') or []\n"
    "limits_applied = False\n"
    "for index, case in enumerate(cases):\n"
    "    try:\n"
    "        result = _run_restricted(\n"
    "            payload['code'], case,\n"
    "            memory_limit_mb=payload.get('memory_limit_mb'),\n"
    "            max_output_chars=payload.get('max_output_chars'),\n"
    "            apply_limits=not limits_applied,\n"
    "        )\n"
    "    except BaseException as exc:  # noqa: BLE001 — SystemExit/KeyboardInterrupt студента\n"
    "        result = {\n"
    "            'success': False, 'output': '',\n"
    "            'error': f'{type(exc).__name__}: {exc}',\n"
    "            'error_type': type(exc).__name__,\n"
    "        }\n"
    "    limits_applied = True\n"
    "    result['index'] = index\n"
    "    sys.stdout.write(json.dumps(result, ensure_ascii=False) + '\\n')\n"
    "    sys.stdout.flush()\n"
)

#: Тёплый воркер пула (S23-002): читает построчные запросы, на каждый пишет
#: строки результатов + строку-терминатор `{"done": true}`. Процесс живёт
#: между задачами, поэтому лимит памяти ставится один раз (RLIMIT/Job Object
#: нельзя ослабить). Изоляция задач — свежие globals на каждый вызов
#: `_run_restricted`, как в батчевом раннере.
_POOL_WORKER = (
    "import json, sys\n"
    "from app.core.executor import _run_restricted\n"
    "limits_applied = False\n"
    "while True:\n"
    "    line = sys.stdin.readline()\n"
    "    if not line:\n"
    "        break\n"
    "    payload = json.loads(line)\n"
    "    if payload.get('shutdown'):\n"
    "        break\n"
    "    cases = payload.get('cases') or []\n"
    "    for index, case in enumerate(cases):\n"
    "        try:\n"
    "            result = _run_restricted(\n"
    "                payload['code'], case,\n"
    "                memory_limit_mb=payload.get('memory_limit_mb'),\n"
    "                max_output_chars=payload.get('max_output_chars'),\n"
    "                apply_limits=not limits_applied,\n"
    "            )\n"
    "        except BaseException as exc:  # noqa: BLE001\n"
    "            result = {\n"
    "                'success': False, 'output': '',\n"
    "                'error': f'{type(exc).__name__}: {exc}',\n"
    "                'error_type': type(exc).__name__,\n"
    "            }\n"
    "        limits_applied = True\n"
    "        result['index'] = index\n"
    "        sys.stdout.write(json.dumps(result, ensure_ascii=False) + '\\n')\n"
    "    sys.stdout.write('{\"done\": true}\\n')\n"
    "    sys.stdout.flush()\n"
)


#: Общий на процесс ограничитель одновременных запусков (S13-003).
#: Semaphore из `asyncio` нельзя переиспользовать между event loop'ами
#: (pytest создаёт новый loop на тест), поэтому используем threading.
_executor_slots: tuple[int, threading.BoundedSemaphore] | None = None
_slots_lock = threading.Lock()


def _get_executor_slots(limit: int) -> threading.BoundedSemaphore:
    """Вернуть общий семафор на `limit` одновременных запусков"""
    global _executor_slots
    normalized = max(1, limit)
    with _slots_lock:
        if _executor_slots is None or _executor_slots[0] != normalized:
            _executor_slots = (normalized, threading.BoundedSemaphore(normalized))
        return _executor_slots[1]


def reset_executor_slots() -> None:
    """Сбросить семафор (тесты)"""
    global _executor_slots
    with _slots_lock:
        _executor_slots = None


class SandboxedExecutor:
    """Песочница для кода ученика"""

    def __init__(
        self,
        timeout: float = 5.0,
        memory_limit_mb: int | None = None,
        max_output_chars: int | None = None,
        max_concurrency: int | None = None,
        queue_timeout: float | None = None,
        pool_size: int | None = None,
        pool_max_tasks: int | None = None,
        mode: str | None = None,
        image: str | None = None,
    ) -> None:
        self.timeout = timeout
        self.memory_limit_mb = (
            settings.executor_memory_limit
            if memory_limit_mb is None
            else memory_limit_mb
        )
        self.max_output_chars = (
            settings.executor_max_output
            if max_output_chars is None
            else max_output_chars
        )
        self.max_concurrency = max(
            1,
            settings.executor_max_concurrency
            if max_concurrency is None
            else max_concurrency,
        )
        self.queue_timeout = (
            settings.executor_queue_timeout
            if queue_timeout is None
            else queue_timeout
        )
        #: Пул тёплых интерпретаторов (S23-002); 0 — выключен
        self.pool_size = (
            settings.executor_pool_size if pool_size is None else max(0, pool_size)
        )
        self.pool_max_tasks = max(
            1,
            settings.executor_pool_max_tasks
            if pool_max_tasks is None
            else pool_max_tasks,
        )
        #: Режим исполнения (S24): `native` или `container`
        self.mode = (mode or settings.executor_mode).strip().lower()
        self.image = image or settings.executor_image

    def _execute_in_process(self, code: str, stdin_text: str = "") -> ExecutionResult:
        """Запустить код в отдельном интерпретаторе и дождаться результата"""
        env = {
            **os.environ,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONPATH": str(BACKEND_DIR),
        }
        payload = json.dumps(
            {
                "code": code,
                "stdin": stdin_text,
                "memory_limit_mb": self.memory_limit_mb,
                "max_output_chars": self.max_output_chars,
            },
            ensure_ascii=False,
        )
        started = time.perf_counter()

        try:
            completed = subprocess.run(  # noqa: S603 — фиксированная команда
                [sys.executable, "-c", _RUNNER],
                input=payload.encode("utf-8"),
                capture_output=True,
                timeout=self.timeout,
                cwd=str(BACKEND_DIR),
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                error=f"Превышен лимит времени выполнения ({self.timeout:.0f} с)",
                error_type="TimeoutError",
                execution_time=time.perf_counter() - started,
            )

        elapsed = time.perf_counter() - started
        stdout = completed.stdout.decode("utf-8", errors="replace").strip()

        try:
            raw: dict[str, Any] = json.loads(stdout)
        except json.JSONDecodeError:
            stderr = completed.stderr.decode("utf-8", errors="replace").strip()
            return ExecutionResult(
                success=False,
                error=f"Сбой песочницы: {stderr[-500:] or 'нет ответа'}",
                error_type="SandboxError",
                execution_time=elapsed,
            )

        return self._result_from_payload(raw, elapsed)

    @staticmethod
    def _result_from_payload(raw: dict[str, Any], elapsed: float) -> ExecutionResult:
        """Разобрать JSON-ответ раннера в `ExecutionResult`"""
        return ExecutionResult(
            success=bool(raw.get("success")),
            output=str(raw.get("output", "")),
            error=raw.get("error"),
            execution_time=float(raw.get("execution_time") or elapsed),
            error_type=raw.get("error_type"),
            violations=list(raw.get("violations") or []),
            memory_limit_enforced=bool(raw.get("memory_limit_enforced")),
            output_truncated=bool(raw.get("output_truncated")),
        )

    @staticmethod
    def _runner_env() -> dict[str, str]:
        """Окружение дочернего интерпретатора"""
        return {
            **os.environ,
            "PYTHONIOENCODING": "utf-8",
            "PYTHONPATH": str(BACKEND_DIR),
        }

    @staticmethod
    async def _stop_process(process: asyncio.subprocess.Process) -> None:
        """Гарантированно завершить дочерний процесс (S23-001).

        Даём процессу шанс выйти самому (нормальный путь), затем убиваем.
        """
        if process.returncode is None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(process.wait(), timeout=1.0)
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                process.kill()
        if process.returncode is None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(process.wait(), timeout=5)

    async def _execute_batch_process(
        self, code: str, stdins: list[str]
    ) -> list[ExecutionResult] | None:
        """Один интерпретатор — все кейсы; `None` — протокол не заработал.

        Таймаут ставится на **каждый кейс** (построчный прогресс), поэтому
        зависший кейс не «съедает» весь батч: процесс убивается, текущий кейс
        получает `TimeoutError`, остальные — `SandboxError` (не выполнялись).
        """
        payload = json.dumps(
            {
                "code": code,
                "cases": list(stdins),
                "memory_limit_mb": self.memory_limit_mb,
                "max_output_chars": self.max_output_chars,
            },
            ensure_ascii=False,
        )
        started = time.perf_counter()

        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                _BATCH_RUNNER,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(BACKEND_DIR),
                env=self._runner_env(),
            )
        except (NotImplementedError, OSError):
            # Нет поддержки subprocess в текущем event loop / ОС — fallback.
            return None

        assert process.stdin is not None
        assert process.stdout is not None

        results: list[ExecutionResult | None] = [None] * len(stdins)
        try:
            process.stdin.write(payload.encode("utf-8"))
            await process.stdin.drain()
            process.stdin.close()

            for index in range(len(stdins)):
                try:
                    line = await asyncio.wait_for(
                        process.stdout.readline(), timeout=self.timeout
                    )
                except TimeoutError:
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
        finally:
            # Сначала гасим процесс, потом читаем stderr: читать раньше —
            # значит ждать EOF от ещё живого интерпретатора (зависший кейс →
            # вечное ожидание).
            await self._stop_process(process)
            stderr_text = ""
            if process.stderr is not None:
                with contextlib.suppress(Exception):
                    stderr_text = (
                        await asyncio.wait_for(process.stderr.read(), timeout=5)
                    ).decode("utf-8", errors="replace").strip()

        if all(result is None for result in results):
            # Дочерний процесс не выдал ни строки — возможно, не смог
            # импортировать приложение (например, чужой venv). Ведём себя как
            # раньше: последовательный путь по кейсам.
            return None

        fallback_error = f"Сбой песочницы: {stderr_text[-500:] or 'нет ответа'}"
        for index, result in enumerate(results):
            if result is None:
                results[index] = ExecutionResult(
                    success=False,
                    error=fallback_error,
                    error_type="SandboxError",
                    execution_time=time.perf_counter() - started,
                )
        return [result for result in results if result is not None]

    @staticmethod
    async def spawn_pool_worker() -> asyncio.subprocess.Process:
        """Поднять процесс пула (S23-002)"""
        return await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            _POOL_WORKER,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            # stderr не читаем: иначе предупреждения компилятора заполнят pipe и
            # заблокируют долгоживущий процесс.
            stderr=asyncio.subprocess.DEVNULL,
            cwd=str(BACKEND_DIR),
            env=SandboxedExecutor._runner_env(),
        )

    async def _execute_batch_on_worker(
        self, worker: PooledWorker, code: str, stdins: list[str]
    ) -> tuple[list[ExecutionResult], bool]:
        """Батч в тёплом процессе: `(результаты, можно ли переиспользовать)`"""
        process = worker.process
        assert process.stdin is not None
        assert process.stdout is not None

        payload = json.dumps(
            {
                "code": code,
                "cases": list(stdins),
                "memory_limit_mb": self.memory_limit_mb,
                "max_output_chars": self.max_output_chars,
            },
            ensure_ascii=False,
        )
        started = time.perf_counter()

        try:
            process.stdin.write((payload + "\n").encode("utf-8"))
            await process.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            return (
                [
                    ExecutionResult(
                        success=False,
                        error="Сбой песочницы: процесс завершился",
                        error_type="SandboxError",
                    )
                    for _ in stdins
                ],
                False,
            )

        results: list[ExecutionResult | None] = [None] * len(stdins)
        reusable = True

        for index in range(len(stdins)):
            try:
                line = await asyncio.wait_for(
                    process.stdout.readline(), timeout=self.timeout
                )
            except TimeoutError:
                results[index] = ExecutionResult(
                    success=False,
                    error=(
                        "Превышен лимит времени выполнения "
                        f"({self.timeout:.0f} с)"
                    ),
                    error_type="TimeoutError",
                    execution_time=time.perf_counter() - started,
                )
                reusable = False
                break
            if not line:
                reusable = False
                break
            try:
                raw = json.loads(line.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                reusable = False
                break
            if not isinstance(raw, dict):
                reusable = False
                break
            results[index] = self._result_from_payload(
                raw, time.perf_counter() - started
            )

        # Терминатор выравнивает поток; без него процесс нельзя переиспользовать.
        if reusable and all(result is not None for result in results):
            try:
                terminator = await asyncio.wait_for(
                    process.stdout.readline(), timeout=self.timeout
                )
                reusable = bool(terminator)
            except TimeoutError:
                reusable = False

        if any(result is None for result in results):
            reusable = False
            fallback_error = "Сбой песочницы: нет ответа воркера"
            for index, result in enumerate(results):
                if result is None:
                    results[index] = ExecutionResult(
                        success=False,
                        error=fallback_error,
                        error_type="SandboxError",
                        execution_time=time.perf_counter() - started,
                    )

        return [result for result in results if result is not None], reusable

    async def _execute_in_container(
        self, code: str, stdins: list[str]
    ) -> list[ExecutionResult] | None:
        """Батч в контейнере (S24); `None` — Docker недоступен, откат на native"""
        sandbox = ContainerSandbox(
            image=self.image,
            timeout=self.timeout,
            memory_limit_mb=self.memory_limit_mb,
            max_output_chars=self.max_output_chars,
        )
        return await sandbox.run_batch(code, stdins)

    async def execute_many(
        self, code: str, stdins: list[str]
    ) -> list[ExecutionResult]:
        """Выполнить код для нескольких stdin (S23-001/S23-002).

        При включённом пуле (`EXECUTOR_POOL_SIZE > 0`) батч идёт в тёплом
        процессе и возвращается в пул; после таймаута/сбоя процесс убивается.
        Иначе — одноразовый батчевый процесс, с последовательным fallback.
        Один слот `max_concurrency` занимает весь батч (это один процесс).
        """
        if not stdins:
            return []

        slots = _get_executor_slots(self.max_concurrency)
        acquired = await asyncio.to_thread(slots.acquire, True, self.queue_timeout)
        if not acquired:
            raise ServiceUnavailableError(
                "Песочница перегружена: слишком много одновременных запусков. "
                "Попробуйте через несколько секунд."
            )
        started_at = time.perf_counter()
        try:
            # S24: контейнерный режим — до пула/батча; при недоступном Docker
            # `run_batch` вернёт None, и мы продолжим нативным путём.
            if self.mode == "container":
                container_results = await self._execute_in_container(code, stdins)
                if container_results is not None:
                    self._observe_sandbox(started_at, "container", container_results)
                    return container_results

            if self.pool_size > 0:
                try:
                    pool = get_pool(self.pool_size, self.pool_max_tasks)
                    worker = await pool.acquire()
                except (NotImplementedError, OSError):
                    worker = None
                if worker is not None:
                    reusable = False
                    try:
                        results, reusable = await self._execute_batch_on_worker(
                            worker, code, stdins
                        )
                        self._observe_sandbox(started_at, "native", results)
                        return results
                    finally:
                        await pool.release(worker, reusable=reusable)

            batched = await self._execute_batch_process(code, stdins)
            results = (
                batched
                if batched is not None
                else [self._execute_in_process(code, stdin) for stdin in stdins]
            )
            self._observe_sandbox(started_at, "native", results)
            return results
        finally:
            slots.release()

    @staticmethod
    def _observe_sandbox(
        started_at: float, mode: str, results: list[ExecutionResult]
    ) -> None:
        """Метрики песочницы (S25-002): длительность, результат, таймауты"""
        sandbox_observed(
            mode=mode,
            duration_s=time.perf_counter() - started_at,
            timed_out=any(result.error_type == "TimeoutError" for result in results),
            failed=any(not result.success for result in results),
        )

    async def execute(self, code: str, stdin_text: str = "") -> ExecutionResult:
        """Выполнить код в песочнице (блокирующая работа — в отдельном потоке).

        Одновременных запусков не больше `max_concurrency`; если слот не
        освободился за `queue_timeout`, возвращается 503 (S13-003).
        """
        slots = _get_executor_slots(self.max_concurrency)
        acquired = await asyncio.to_thread(slots.acquire, True, self.queue_timeout)
        if not acquired:
            raise ServiceUnavailableError(
                "Песочница перегружена: слишком много одновременных запусков. "
                "Попробуйте через несколько секунд."
            )
        try:
            return await asyncio.to_thread(self._execute_in_process, code, stdin_text)
        finally:
            slots.release()
