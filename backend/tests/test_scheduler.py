"""Тесты встроенного планировщика retention (KI-025)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time

import pytest

from app.config import Settings, settings
from app.core import metrics
from app.services import scheduler as scheduler_module
from app.services.retention import RetentionTable


class _FakeSession:
    """Заглушка AsyncSession: run_retention_once использует её как контекст"""

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


@pytest.fixture
def fake_session_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Подменить фабрику сессий в модуле планировщика"""
    monkeypatch.setattr(
        scheduler_module, "async_session_factory", lambda: _FakeSession()
    )


# --- разбор времени запуска -------------------------------------------------


def test_parse_run_at_valid() -> None:
    assert scheduler_module.parse_run_at("03:30") == time(3, 30)
    assert scheduler_module.parse_run_at(" 23:59 ") == time(23, 59)


@pytest.mark.parametrize("value", ["25:00", "ab:cd", "", "3.5:10"])
def test_parse_run_at_invalid_falls_back(value: str) -> None:
    assert scheduler_module.parse_run_at(value) == scheduler_module.FALLBACK_RUN_AT


# --- расчёт задержки --------------------------------------------------------


def test_seconds_until_next_run_same_day() -> None:
    now = datetime(2026, 11, 3, 1, 0, tzinfo=UTC)

    assert scheduler_module.seconds_until_next_run(now, time(3, 30)) == 2.5 * 3600


def test_seconds_until_next_run_next_day() -> None:
    now = datetime(2026, 11, 3, 10, 0, tzinfo=UTC)

    assert scheduler_module.seconds_until_next_run(now, time(3, 30)) == 17.5 * 3600


def test_seconds_until_next_run_exact_boundary_is_tomorrow() -> None:
    now = datetime(2026, 11, 3, 3, 30, tzinfo=UTC)

    assert scheduler_module.seconds_until_next_run(now, time(3, 30)) == 24 * 3600


# --- один прогон под advisory-lock ------------------------------------------


async def test_run_retention_once_skips_when_lock_held(
    monkeypatch: pytest.MonkeyPatch, fake_session_factory: None
) -> None:
    calls: list[dict[str, object]] = []

    async def fake_apply(**kwargs: object) -> dict[str, int]:
        calls.append(dict(kwargs))
        return {}

    async def busy(_session: object) -> bool:
        return False

    monkeypatch.setattr(scheduler_module, "apply_retention", fake_apply)
    monkeypatch.setattr(scheduler_module, "_acquire_lock", busy)

    assert await scheduler_module.run_retention_once(batch_size=10) is None
    assert calls == []


async def test_run_retention_once_runs_and_releases_lock(
    monkeypatch: pytest.MonkeyPatch, fake_session_factory: None
) -> None:
    released: list[bool] = []
    received: list[dict[str, object]] = []

    async def applied(**kwargs: object) -> dict[str, int]:
        received.append(dict(kwargs))
        return {"chat_messages": 2}

    async def acquire(_session: object) -> bool:
        return True

    async def release(_session: object) -> None:
        released.append(True)

    monkeypatch.setattr(scheduler_module, "apply_retention", applied)
    monkeypatch.setattr(scheduler_module, "_acquire_lock", acquire)
    monkeypatch.setattr(scheduler_module, "_release_lock", release)

    result = await scheduler_module.run_retention_once(batch_size=500)

    assert result == {"chat_messages": 2}
    assert received == [{"dry_run": False, "only": None, "batch_size": 500}]
    assert released == [True]


async def test_run_retention_once_releases_lock_on_error(
    monkeypatch: pytest.MonkeyPatch, fake_session_factory: None
) -> None:
    released: list[bool] = []

    async def broken(**_kwargs: object) -> dict[str, int]:
        raise RuntimeError("db down")

    async def acquire(_session: object) -> bool:
        return True

    async def release(_session: object) -> None:
        released.append(True)

    monkeypatch.setattr(scheduler_module, "apply_retention", broken)
    monkeypatch.setattr(scheduler_module, "_acquire_lock", acquire)
    monkeypatch.setattr(scheduler_module, "_release_lock", release)

    with pytest.raises(RuntimeError, match="db down"):
        await scheduler_module.run_retention_once()

    assert released == [True]


# --- цикл планировщика ------------------------------------------------------


async def test_scheduler_loop_runs_once_and_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    stop = asyncio.Event()
    runs: list[int] = []

    async def fake_run(*, batch_size: int = 0) -> dict[str, int]:
        runs.append(batch_size)
        stop.set()
        return {}

    monkeypatch.setattr(scheduler_module, "run_retention_once", fake_run)
    monkeypatch.setattr(
        scheduler_module, "seconds_until_next_run", lambda _now, _at: 0.0
    )

    await asyncio.wait_for(scheduler_module.scheduler_loop(stop=stop), timeout=5)

    assert runs == [scheduler_module.DEFAULT_BATCH_SIZE]


async def test_scheduler_loop_does_not_run_when_stopped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stop = asyncio.Event()
    stop.set()
    runs: list[object] = []

    async def fake_run(**_kwargs: object) -> dict[str, int]:
        runs.append(object())
        return {}

    monkeypatch.setattr(scheduler_module, "run_retention_once", fake_run)

    await asyncio.wait_for(scheduler_module.scheduler_loop(stop=stop), timeout=5)

    assert runs == []


async def test_scheduler_loop_survives_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    stop = asyncio.Event()
    attempts: list[int] = []

    async def always_fail(**_kwargs: object) -> dict[str, int]:
        attempts.append(1)
        raise RuntimeError("db down")

    delays = iter([0.0, 0.0])

    def fake_delay(_now: datetime, _at: time) -> float:
        try:
            return next(delays)
        except StopIteration:
            stop.set()
            return 3600.0

    monkeypatch.setattr(scheduler_module, "run_retention_once", always_fail)
    monkeypatch.setattr(scheduler_module, "seconds_until_next_run", fake_delay)

    await asyncio.wait_for(scheduler_module.scheduler_loop(stop=stop), timeout=5)

    assert attempts  # прогон был, исключение поймано, цикл завершился штатно


# --- запуск/остановка из lifespan ------------------------------------------


async def test_stop_scheduler_none_is_noop() -> None:
    await scheduler_module.stop_scheduler(None)


async def test_start_and_stop_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "retention_scheduler_at", "03:30")

    handle = scheduler_module.start_scheduler(batch_size=100)
    await scheduler_module.stop_scheduler(handle)

    assert handle.task.done()


def test_scheduler_settings_defaults() -> None:
    defaults = Settings.model_fields

    assert defaults["retention_scheduler_enabled"].default is False
    assert defaults["retention_scheduler_at"].default == "03:30"
    assert defaults["retention_scheduler_batch_size"].default == 1000


# --- счётчики retention -----------------------------------------------------


async def test_retention_counters_increment(
    monkeypatch: pytest.MonkeyPatch, db_session: object
) -> None:
    from app.services import retention as retention_module

    class _SessionCtx:
        async def __aenter__(self) -> object:
            return db_session

        async def __aexit__(self, *exc_info: object) -> bool:
            return False

    calls: dict[str, int] = {}

    async def fake_delete(
        _db: object, table: RetentionTable, _cutoff: object, _batch_size: int
    ) -> int:
        calls[table.name] = calls.get(table.name, 0) + 1
        return 2 if calls[table.name] == 1 else 0

    metrics.reset_metrics()
    monkeypatch.setattr(
        retention_module, "async_session_factory", lambda: _SessionCtx()
    )
    monkeypatch.setattr(retention_module, "_delete_batch", fake_delete)

    await retention_module.apply_retention(dry_run=False, only=None, batch_size=100)

    rows = metrics.registry.get_sample_value(
        "retention_rows_deleted_total", {"table": "chat_messages"}
    )
    runs = metrics.registry.get_sample_value(
        "retention_runs_total", {"table": "chat_messages", "result": "applied"}
    )
    assert rows == 2
    assert runs == 1
