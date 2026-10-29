"""
Репозитории задач и прогресса (S7-001).
"""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.task import Task, TaskDifficulty, UserTaskProgress


class TaskRepository(BaseRepository[Task]):
    """Работа с задачами"""

    def __init__(self, session: AsyncSession):
        super().__init__(Task, session)

    async def list_tasks(
        self,
        *,
        difficulty: TaskDifficulty | None = None,
        category: str | None = None,
        only_active: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Task]:
        """Список задач с фильтрами"""
        query = select(Task)
        if only_active:
            query = query.where(Task.is_active.is_(True))
        if difficulty is not None:
            query = query.where(Task.difficulty == difficulty)
        if category is not None:
            query = query.where(Task.category == category)
        query = query.order_by(Task.created_at.asc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_by_difficulty(self) -> dict[str, int]:
        """Количество задач по сложностям"""
        result = await self.session.execute(
            select(Task.difficulty, func.count())
            .where(Task.is_active.is_(True))
            .group_by(Task.difficulty)
        )
        return {str(difficulty.value): count for difficulty, count in result.all()}

    async def count_by_category(self) -> dict[str, int]:
        """Количество задач по категориям"""
        result = await self.session.execute(
            select(Task.category, func.count())
            .where(Task.is_active.is_(True))
            .group_by(Task.category)
        )
        # row[0]/row[1] вместо распаковки: dict(result.all()) требует
        # Iterable[tuple], а SQLAlchemy возвращает Sequence[Row]
        return {row[0]: row[1] for row in result.all()}


class ProgressRepository(BaseRepository[UserTaskProgress]):
    """Работа с прогрессом ученика"""

    def __init__(self, session: AsyncSession):
        super().__init__(UserTaskProgress, session)

    async def get_by_user_and_task(
        self, user_id: UUID, task_id: UUID
    ) -> UserTaskProgress | None:
        """Прогресс по конкретной задаче"""
        result = await self.session.execute(
            select(UserTaskProgress).where(
                UserTaskProgress.user_id == user_id,
                UserTaskProgress.task_id == task_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_user_progress(self, user_id: UUID) -> list[UserTaskProgress]:
        """Весь прогресс пользователя"""
        result = await self.session.execute(
            select(UserTaskProgress).where(UserTaskProgress.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_user_progress_map(self, user_id: UUID) -> dict[UUID, UserTaskProgress]:
        """Прогресс пользователя в виде словаря task_id → запись"""
        items = await self.get_user_progress(user_id)
        return {item.task_id: item for item in items}

    async def count_attempts(self, user_id: UUID) -> int:
        """Суммарное число попыток пользователя"""
        result = await self.session.execute(
            select(func.coalesce(func.sum(UserTaskProgress.attempts), 0)).where(
                UserTaskProgress.user_id == user_id
            )
        )
        return int(result.scalar_one())

    async def exists_for_task(self, task_id: UUID) -> bool:
        """Есть ли хоть один прогресс по задаче (для мягкого удаления)"""
        result = await self.session.execute(
            select(UserTaskProgress.id).where(UserTaskProgress.task_id == task_id).limit(1)
        )
        return result.scalar_one_or_none() is not None
