"""
Репозитории задач и прогресса (S7-001).
"""

from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.repositories.base import BaseRepository
from app.models.task import (
    Task,
    TaskAttempt,
    TaskDifficulty,
    TaskStatus,
    TaskVersion,
    UserTaskProgress,
)


class TaskRepository(BaseRepository[Task]):
    """Работа с задачами"""

    def __init__(self, session: AsyncSession):
        super().__init__(Task, session)

    async def list_tasks(
        self,
        *,
        difficulty: TaskDifficulty | None = None,
        category: str | None = None,
        tag: str | None = None,
        search: str | None = None,
        only_active: bool = True,
        skip: int = 0,
        limit: int = 100,
        user_id: UUID | None = None,
        status: TaskStatus | None = None,
    ) -> list[Task]:
        """Список задач с фильтрами (теги — JSONB, поиск — ILIKE)

        Фильтр `status` отбирает задачи по прогрессу конкретного
        ученика (`user_id` обязателен вместе с ним): у `not_started`
        подходит задача и без записи прогресса, и с записью в этом
        статусе.
        """
        query = select(Task)
        if only_active:
            query = query.where(Task.is_active.is_(True))
        if difficulty is not None:
            query = query.where(Task.difficulty == difficulty)
        if category is not None:
            query = query.where(Task.category == category)
        if tag:
            query = query.where(Task.tags.contains([tag.strip().lower()]))
        if search:
            pattern = f"%{search.strip().lower()}%"
            query = query.where(
                or_(
                    func.lower(Task.title).like(pattern),
                    func.lower(Task.description).like(pattern),
                )
            )
        if status is not None:
            if user_id is None:
                raise ValueError("Фильтр по статусу требует user_id")
            progress = aliased(UserTaskProgress)
            query = query.outerjoin(
                progress,
                and_(
                    progress.task_id == Task.id,
                    progress.user_id == user_id,
                ),
            )
            if status == TaskStatus.NOT_STARTED:
                query = query.where(
                    or_(
                        progress.id.is_(None),
                        progress.status == TaskStatus.NOT_STARTED,
                    )
                )
            else:
                query = query.where(progress.status == status)
        query = query.order_by(Task.created_at.asc()).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_categories(self) -> list[str]:
        """Уникальные категории активных задач"""
        result = await self.session.execute(
            select(Task.category)
            .where(Task.is_active.is_(True))
            .distinct()
            .order_by(Task.category)
        )
        return [str(row[0]) for row in result.all()]

    async def count_tasks(self, *, only_active: bool = True) -> int:
        """Общее число задач (для пагинации, S19-004)"""
        query = select(func.count()).select_from(Task)
        if only_active:
            query = query.where(Task.is_active.is_(True))
        result = await self.session.execute(query)
        return int(result.scalar_one())

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


class TaskAttemptRepository(BaseRepository[TaskAttempt]):
    """История попыток ученика по задаче (S42-002)"""

    def __init__(self, session: AsyncSession):
        super().__init__(TaskAttempt, session)

    async def list_for_user_and_task(
        self, user_id: UUID, task_id: UUID, skip: int = 0, limit: int = 20
    ) -> list[TaskAttempt]:
        """Попытки ученика по задаче (новые сверху)"""
        result = await self.session.execute(
            select(TaskAttempt)
            .where(
                TaskAttempt.user_id == user_id,
                TaskAttempt.task_id == task_id,
            )
            .order_by(TaskAttempt.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_for_user_and_task(
        self, user_id: UUID, task_id: UUID
    ) -> int:
        """Всего попыток ученика по задаче"""
        result = await self.session.execute(
            select(func.count())
            .select_from(TaskAttempt)
            .where(
                TaskAttempt.user_id == user_id,
                TaskAttempt.task_id == task_id,
            )
        )
        return int(result.scalar_one())


class TaskVersionRepository(BaseRepository[TaskVersion]):
    """История версий задач (S14-005)"""

    def __init__(self, session: AsyncSession):
        super().__init__(TaskVersion, session)

    async def list_for_task(self, task_id: UUID) -> list[TaskVersion]:
        """Версии задачи (новые сверху)"""
        result = await self.session.execute(
            select(TaskVersion)
            .where(TaskVersion.task_id == task_id)
            .order_by(TaskVersion.version.desc())
        )
        return list(result.scalars().all())

    async def latest_version(self, task_id: UUID) -> int:
        """Номер последней версии (0, если истории нет)"""
        result = await self.session.execute(
            select(func.max(TaskVersion.version)).where(
                TaskVersion.task_id == task_id
            )
        )
        return int(result.scalar_one() or 0)

    async def get_by_version(
        self, task_id: UUID, version: int
    ) -> TaskVersion | None:
        """Конкретная версия задачи"""
        result = await self.session.execute(
            select(TaskVersion).where(
                TaskVersion.task_id == task_id,
                TaskVersion.version == version,
            )
        )
        return result.scalar_one_or_none()
