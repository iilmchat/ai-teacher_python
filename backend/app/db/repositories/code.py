"""
Репозиторий истории выполнений кода.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.base import BaseRepository
from app.models.code import CodeExecution


class CodeExecutionRepository(BaseRepository[CodeExecution]):
    """Работа с историей запусков кода"""

    def __init__(self, session: AsyncSession):
        super().__init__(CodeExecution, session)

    async def get_user_executions(
        self, user_id: UUID, skip: int = 0, limit: int = 20
    ) -> list[CodeExecution]:
        """Последние запуски пользователя"""
        result = await self.session.execute(
            select(CodeExecution)
            .where(CodeExecution.user_id == user_id)
            .order_by(CodeExecution.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
