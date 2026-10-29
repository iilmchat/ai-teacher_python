"""
Аналитика для админ-панели (S10-005).

Все запросы — агрегаты по существующим таблицам; отдельного хранилища
метрик нет, чтобы не усложнять схему.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession
from app.models.code import CodeExecution
from app.models.task import Task, TaskStatus, UserTaskProgress
from app.models.user import User, UserRole


class AnalyticsService:
    """Сводные метрики системы и активности учеников"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _count(self, query: Select[Any]) -> int:
        result = await self.db.execute(query)
        return int(result.scalar_one() or 0)

    async def users_by_role(self) -> dict[str, int]:
        """Количество пользователей по ролям"""
        result = await self.db.execute(
            select(User.role, func.count()).group_by(User.role)
        )
        counts = {role.value: 0 for role in UserRole}
        for role, count in result.all():
            counts[role.value] = int(count)
        return counts

    async def active_users(self, hours: int = 24) -> int:
        """Пользователи, активные за последние N часов"""
        threshold = datetime.utcnow() - timedelta(hours=hours)
        return await self._count(
            select(func.count()).select_from(User).where(User.last_active >= threshold)
        )

    async def tasks_overview(self) -> dict[str, int]:
        """Задачи по сложности и статусу активности"""
        result = await self.db.execute(
            select(Task.difficulty, func.count()).group_by(Task.difficulty)
        )
        by_difficulty = {difficulty: int(count) for difficulty, count in result.all()}
        active = await self._count(
            select(func.count()).select_from(Task).where(Task.is_active.is_(True))
        )
        total = await self._count(select(func.count()).select_from(Task))
        return {
            "total": total,
            "active": active,
            "easy": by_difficulty.get("easy", 0),
            "medium": by_difficulty.get("medium", 0),
            "hard": by_difficulty.get("hard", 0),
        }

    async def learning_overview(self) -> dict[str, float | int]:
        """Прогресс обучения: попытки, завершения, среднее число попыток"""
        attempts = await self._count(
            select(func.coalesce(func.sum(UserTaskProgress.attempts), 0))
        )
        completed = await self._count(
            select(func.count())
            .select_from(UserTaskProgress)
            .where(UserTaskProgress.status == TaskStatus.COMPLETED)
        )
        started = await self._count(
            select(func.count()).select_from(UserTaskProgress)
        )
        average_attempts = round(attempts / started, 2) if started else 0.0
        return {
            "attempts": attempts,
            "completed": completed,
            "started": started,
            "average_attempts": average_attempts,
        }

    async def chat_overview(self) -> dict[str, int]:
        """Активность чата и песочницы"""
        sessions = await self._count(select(func.count()).select_from(ChatSession))
        messages = await self._count(select(func.count()).select_from(ChatMessage))
        executions = await self._count(select(func.count()).select_from(CodeExecution))
        failed_executions = await self._count(
            select(func.count())
            .select_from(CodeExecution)
            .where(CodeExecution.success.is_(False))
        )
        return {
            "sessions": sessions,
            "messages": messages,
            "executions": executions,
            "failed_executions": failed_executions,
        }

    async def summary(self) -> dict[str, object]:
        """Полная сводка для дашборда"""
        users_by_role = await self.users_by_role()
        return {
            "users": {
                "total": sum(users_by_role.values()),
                "by_role": users_by_role,
                "active_24h": await self.active_users(24),
                "active_7d": await self.active_users(24 * 7),
            },
            "tasks": await self.tasks_overview(),
            "learning": await self.learning_overview(),
            "activity": await self.chat_overview(),
            "generated_at": datetime.utcnow().isoformat(),
        }
