"""Пул «тёплых» интерпретаторов песочницы (S23-002, KI-022).

Батчевый раннер (S23-001) убирает повторный старт интерпретатора на каждый
тест-кейс, но каждый submit всё ещё платит ~0.3–0.4 с за импорт приложения и
RestrictedPython. Пул держит несколько уже поднятых процессов и переиспользует
их между задачами.

Изоляция:

* на каждую задачу/кейс `_run_restricted` создаёт свежие globals и builtins,
  поэтому переменные ученика не «протекают» между задачами;
* лимит памяти ставится один раз на процесс (RLIMIT_AS/Job Object нельзя
  ослабить или навесить дважды) — это документированное поведение;
* процесс перезапускается после `max_tasks` задач, после таймаута и после
  любого сбоя протокола: «залипшая» песочница не переиспользуется.

Пул — module-level и привязан к event loop: pytest создаёт новый loop на тест,
поэтому процессы чужого loop закрываются при первом обращении из нового.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class PooledWorker:
    """Один переиспользуемый интерпретатор"""

    process: asyncio.subprocess.Process
    loop: asyncio.AbstractEventLoop
    tasks: int = 0
    created_at: float = field(default_factory=time.monotonic)


class RunnerPool:
    """Idle-процессы для текущего event loop"""

    def __init__(self, size: int, max_tasks: int) -> None:
        self.size = max(0, size)
        self.max_tasks = max(1, max_tasks)
        self.loop = asyncio.get_running_loop()
        self._idle: list[PooledWorker] = []

    def kill_now(self) -> None:
        """Синхронно убить idle-процессы (закрытый loop, например в pytest)"""
        workers, self._idle = self._idle, []
        for worker in workers:
            with contextlib.suppress(Exception):
                worker.process.kill()

    async def acquire(self) -> PooledWorker:
        """Взять тёплый процесс или поднять новый"""
        loop = asyncio.get_running_loop()
        self._drop_foreign_loops(loop)
        while self._idle:
            worker = self._idle.pop()
            if worker.process.returncode is None:
                return worker
        return await self._spawn(loop)

    async def release(self, worker: PooledWorker, *, reusable: bool) -> None:
        """Вернуть процесс в пул или закрыть его"""
        worker.tasks += 1
        if (
            not reusable
            or worker.process.returncode is not None
            or worker.tasks >= self.max_tasks
            or len(self._idle) >= self.size
        ):
            await _terminate(worker.process)
            return
        self._idle.append(worker)

    async def close(self) -> None:
        """Закрыть все idle-процессы (shutdown приложения/теста)"""
        workers, self._idle = self._idle, []
        for worker in workers:
            await _terminate(worker.process)

    async def _spawn(self, loop: asyncio.AbstractEventLoop) -> PooledWorker:
        # Локальный импорт: executor импортирует этот модуль, обратная
        # зависимость на уровне модулей дала бы цикл.
        from app.core.executor import SandboxedExecutor

        process = await SandboxedExecutor.spawn_pool_worker()
        return PooledWorker(process=process, loop=loop)

    def _drop_foreign_loops(self, loop: asyncio.AbstractEventLoop) -> None:
        """Процессы, поднятые в другом loop (pytest), убиваем синхронно"""
        kept: list[PooledWorker] = []
        for worker in self._idle:
            if worker.loop is loop and worker.process.returncode is None:
                kept.append(worker)
            else:
                with contextlib.suppress(Exception):
                    worker.process.kill()
        self._idle = kept


_lock = threading.Lock()
_pools: dict[int, RunnerPool] = {}


def get_pool(size: int, max_tasks: int) -> RunnerPool:
    """Пул для текущего event loop (создаётся при первом обращении)"""
    loop = asyncio.get_running_loop()
    key = id(loop)
    with _lock:
        # pytest создаёт новый loop на тест: пулы закрытых loop'ов не должны
        # копить живые процессы.
        for stale_key, stale in list(_pools.items()):
            if stale_key != key and stale.loop.is_closed():
                stale.kill_now()
                _pools.pop(stale_key, None)
        pool = _pools.get(key)
        if pool is None:
            pool = RunnerPool(size=size, max_tasks=max_tasks)
            _pools[key] = pool
        return pool


async def close_current_pool() -> None:
    """Закрыть пул текущего loop (вызывается из lifespan)"""
    key = id(asyncio.get_running_loop())
    with _lock:
        pool = _pools.pop(key, None)
    if pool is not None:
        await pool.close()


async def _terminate(process: asyncio.subprocess.Process) -> None:
    """Погасить процесс пула"""
    if process.returncode is None:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            process.kill()
    with contextlib.suppress(Exception):
        await asyncio.wait_for(process.wait(), timeout=5)


#: Экспорт модуля (импорт executor — только внутри `_spawn`, чтобы не было цикла)
__all__ = ["PooledWorker", "RunnerPool", "close_current_pool", "get_pool"]
