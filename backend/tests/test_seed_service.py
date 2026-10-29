"""
Тесты идемпотентного seed задач (S14-002, KI-010).
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.seed_tasks import TASKS
from app.models.task import Task
from app.services.seed_service import seed_tasks


async def test_seed_creates_all_tasks_once(db_session: AsyncSession) -> None:
    """Первый запуск создаёт стартовый набор, второй — ничего"""
    first = await seed_tasks(db_session)
    second = await seed_tasks(db_session)

    total = (
        await db_session.execute(select(func.count()).select_from(Task))
    ).scalar_one()

    assert first == len(TASKS)
    assert second == 0
    assert total == len(TASKS)


async def test_seed_does_not_duplicate_existing_title(
    db_session: AsyncSession,
) -> None:
    """Существующая задача по заголовку не дублируется"""
    await db_session.execute(
        select(Task).where(Task.title == str(TASKS[0]["title"]))
    )
    db_session.add(
        Task(
            title=str(TASKS[0]["title"]),
            description="Уже есть",
            difficulty="easy",  # type: ignore[arg-type]
            category="manual",
            test_cases=[{"input": "", "expected_output": "1"}],
        )
    )
    await db_session.commit()

    created = await seed_tasks(db_session)

    assert created == len(TASKS) - 1
