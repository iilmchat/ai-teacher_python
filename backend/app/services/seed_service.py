"""
Идемпотентное наполнение задач (S14-002, закрывает KI-010).

Используется CLI-скриптом и lifespan приложения при `SEED_ON_START=true`.
Ошибка seed не должна валить старт приложения — вызывающая сторона ловит
исключение и пишет warning.
"""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.seed_tasks import TASKS
from app.models.task import Task
from app.services.cache import invalidate_tasks_cache

logger = structlog.get_logger(__name__)


async def seed_tasks(session: AsyncSession) -> int:
    """Добавить отсутствующие по заголовку задачи; вернуть число созданных"""
    existing = set((await session.execute(select(Task.title))).scalars().all())
    created = 0
    for item in TASKS:
        title = str(item["title"])
        if title in existing:
            continue
        session.add(
            Task(
                title=title,
                description=str(item["description"]),
                difficulty=item["difficulty"],
                category=str(item["category"]),
                test_cases=item["test_cases"],
                hints=item["hints"],
                solution_template=str(item["solution_template"]),
            )
        )
        existing.add(title)
        created += 1
    await session.commit()
    if created:
        await invalidate_tasks_cache()
    logger.info("seed_tasks", created=created, total=len(TASKS))
    return created
