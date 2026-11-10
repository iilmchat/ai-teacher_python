"""Модерация задач (S47-003).

Очередь модерации — только задачи, созданные LLM-генерацией и импортом
(решения D-002/D-003). Ручные задачи учителя публикуются сразу, но модератор
может снять с публикации любую задачу.

Метрики «застревания» считаются по засчитанным попыткам (`task_attempts`) и
сводке прогресса (`user_task_progress`). Запрос — три обращения к БД:
очередь с агрегатами, общее количество и последние попытки выбранной
страницы (без N+1).
"""

from uuid import UUID

from sqlalchemy import Float, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.errors import NotFoundError, ValidationError
from app.models.task import (
    Task,
    TaskAttempt,
    TaskDifficulty,
    TaskSource,
    TaskStatus,
    UserTaskProgress,
)
from app.models.user import User
from app.schemas.admin import (
    AdminTaskReviewItem,
    AdminTaskReviewResponse,
    ModerationAction,
    ModerationAttemptItem,
    ModerationMetrics,
    ModerationSource,
)
from app.services.cache import invalidate_tasks_cache

#: Источники, которые попадают в очередь модерации
REVIEW_SOURCES: tuple[str, str] = (
    TaskSource.GENERATED.value,
    TaskSource.IMPORTED.value,
)

#: Сколько последних попыток показывать в карточке задачи
RECENT_ATTEMPTS_LIMIT = 5


class ModerationService:
    """Очередь модерации и действия модератора"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _queue_conditions(
        source: ModerationSource | None,
        difficulty: TaskDifficulty | None,
    ) -> list[ColumnElement[bool]]:
        """Условия очереди: только generated/imported + фильтры."""
        sources: tuple[str, ...] = (
            (source,) if source is not None else REVIEW_SOURCES
        )
        conditions: list[ColumnElement[bool]] = [Task.source.in_(sources)]
        if difficulty is not None:
            conditions.append(Task.difficulty == difficulty)
        return conditions

    async def list_review_queue(
        self,
        *,
        source: ModerationSource | None = None,
        difficulty: TaskDifficulty | None = None,
        threshold: int = 3,
        skip: int = 0,
        limit: int = 50,
    ) -> AdminTaskReviewResponse:
        """Очередь с метриками; сортировка — «сначала самые проблемные».

        Застрявшим считается ученик, который сделал больше `threshold`
        попыток и так и не завершил задачу.
        """
        conditions = self._queue_conditions(source, difficulty)

        queue = (
            select(
                Task.id,
                Task.title,
                Task.description,
                Task.difficulty,
                Task.category,
                Task.source,
                Task.is_active,
                Task.moderation_comment,
                Task.test_cases,
                Task.hints,
                Task.created_at,
            )
            .where(*conditions)
            .cte("queue")
        )

        attempt_stats = (
            select(
                TaskAttempt.task_id.label("task_id"),
                func.count().label("attempts"),
                func.count().filter(TaskAttempt.passed.is_(True)).label(
                    "passed_attempts"
                ),
            )
            .join(queue, queue.c.id == TaskAttempt.task_id)
            .group_by(TaskAttempt.task_id)
            .cte("attempt_stats")
        )

        progress_stats = (
            select(
                UserTaskProgress.task_id.label("task_id"),
                func.count()
                .filter(UserTaskProgress.attempts > 0)
                .label("students"),
                func.count()
                .filter(
                    UserTaskProgress.attempts > threshold,
                    UserTaskProgress.status != TaskStatus.COMPLETED,
                )
                .label("stuck_students"),
                func.avg(UserTaskProgress.attempts)
                .filter(UserTaskProgress.attempts > 0)
                .label("avg_attempts"),
            )
            .join(queue, queue.c.id == UserTaskProgress.task_id)
            .group_by(UserTaskProgress.task_id)
            .cte("progress_stats")
        )

        attempts = func.coalesce(attempt_stats.c.attempts, 0)
        passed_attempts = func.coalesce(attempt_stats.c.passed_attempts, 0)
        # Доля успеха для ответа: 0 при отсутствии попыток. Для сортировки
        # задачи без попыток уходят вниз (1.0), иначе они «побеждали» бы
        # проблемные с низким процентом успеха.
        success_rate = case(
            (attempts == 0, 0.0),
            else_=cast(passed_attempts, Float) / func.nullif(attempts, 0),
        )
        success_order = case(
            (attempts == 0, 1.0),
            else_=cast(passed_attempts, Float) / func.nullif(attempts, 0),
        )
        students = func.coalesce(progress_stats.c.students, 0)
        stuck_students = func.coalesce(progress_stats.c.stuck_students, 0)
        avg_attempts = func.coalesce(progress_stats.c.avg_attempts, 0.0)

        statement = (
            select(
                queue,
                attempts.label("attempts"),
                passed_attempts.label("passed_attempts"),
                success_rate.label("success_rate"),
                avg_attempts.label("avg_attempts"),
                students.label("students"),
                stuck_students.label("stuck_students"),
            )
            .select_from(
                queue.outerjoin(
                    attempt_stats, attempt_stats.c.task_id == queue.c.id
                ).outerjoin(
                    progress_stats, progress_stats.c.task_id == queue.c.id
                )
            )
            .order_by(
                stuck_students.desc(),
                success_order.asc(),
                attempts.desc(),
                queue.c.created_at.desc(),
            )
            .offset(skip)
            .limit(limit)
        )

        rows = (await self.db.execute(statement)).all()
        recent = await self._recent_attempts([row.id for row in rows])

        items = [
            AdminTaskReviewItem(
                id=row.id,
                title=row.title,
                description=row.description,
                difficulty=row.difficulty,
                category=row.category,
                source=row.source,
                is_active=row.is_active,
                moderation_comment=row.moderation_comment,
                test_cases_count=len(row.test_cases or []),
                hints_count=len(row.hints or []),
                created_at=row.created_at,
                metrics=ModerationMetrics(
                    attempts=int(row.attempts or 0),
                    passed_attempts=int(row.passed_attempts or 0),
                    success_rate=round(float(row.success_rate or 0.0), 4),
                    avg_attempts=round(float(row.avg_attempts or 0.0), 2),
                    students=int(row.students or 0),
                    stuck_students=int(row.stuck_students or 0),
                ),
                recent_attempts=recent.get(row.id, []),
            )
            for row in rows
        ]

        total = int(
            (
                await self.db.execute(
                    select(func.count()).select_from(Task).where(*conditions)
                )
            ).scalar_one()
        )
        return AdminTaskReviewResponse(
            total=total, threshold=threshold, items=items
        )

    async def _recent_attempts(
        self, task_ids: list[UUID]
    ) -> dict[UUID, list[ModerationAttemptItem]]:
        """Последние попытки по задачам страницы — один запрос (S47-003)."""
        if not task_ids:
            return {}

        row_number = (
            func.row_number()
            .over(
                partition_by=TaskAttempt.task_id,
                order_by=TaskAttempt.created_at.desc(),
            )
            .label("row_number")
        )
        ranked = (
            select(
                TaskAttempt.id.label("id"),
                TaskAttempt.task_id.label("task_id"),
                TaskAttempt.user_id.label("user_id"),
                User.username.label("username"),
                TaskAttempt.passed.label("passed"),
                TaskAttempt.passed_count.label("passed_count"),
                TaskAttempt.total_count.label("total_count"),
                TaskAttempt.created_at.label("created_at"),
                row_number,
            )
            .join(User, User.id == TaskAttempt.user_id)
            .where(TaskAttempt.task_id.in_(task_ids))
            .subquery("ranked_attempts")
        )
        statement = (
            select(ranked)
            .where(ranked.c.row_number <= RECENT_ATTEMPTS_LIMIT)
            .order_by(ranked.c.task_id, ranked.c.created_at.desc())
        )
        rows = (await self.db.execute(statement)).all()

        result: dict[UUID, list[ModerationAttemptItem]] = {}
        for row in rows:
            result.setdefault(row.task_id, []).append(
                ModerationAttemptItem(
                    id=row.id,
                    user_id=row.user_id,
                    username=row.username,
                    passed=row.passed,
                    passed_count=row.passed_count,
                    total_count=row.total_count,
                    created_at=row.created_at,
                )
            )
        return result

    async def moderate(
        self,
        task_id: UUID,
        *,
        action: ModerationAction,
        comment: str | None = None,
    ) -> Task:
        """Применить действие модератора и сбросить кэш каталога.

        Ручные задачи (`manual`) в очередь не попадают: для них разрешено
        только снятие с публикации. Публикация и возврат в доработку — для
        `generated`/`imported`.
        """
        task = await self.db.get(Task, task_id)
        if task is None:
            raise NotFoundError("Задача не найдена")

        if task.source == TaskSource.MANUAL.value and action != "unpublish":
            raise ValidationError(
                "Задачи, созданные вручную, не проходят модерацию: "
                "доступно только снятие с публикации"
            )

        if action == "publish":
            task.is_active = True
            task.moderation_comment = None
        elif action == "unpublish":
            task.is_active = False
        else:
            text = (comment or "").strip()
            if not text:
                raise ValidationError(
                    "Комментарий обязателен при возврате в доработку"
                )
            if len(text) > 1000:
                raise ValidationError(
                    "Комментарий не должен превышать 1000 символов"
                )
            task.is_active = False
            task.moderation_comment = text

        await self.db.commit()
        await self.db.refresh(task)
        await invalidate_tasks_cache()
        return task
