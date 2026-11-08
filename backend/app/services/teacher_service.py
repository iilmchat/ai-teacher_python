"""Сервис кабинета учителя (S46): работы учеников и обратная связь.

Доступ к работам ученика есть только у владельца класса, в котором ученик
состоит; администратор видит любого ученика. Проверка вынесена в
`get_student_for_teacher`, чтобы ею пользовались и список попыток, и
комментарии (S46-002).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AccessDeniedError, NotFoundError
from app.models.classroom import Classroom, ClassroomMember
from app.models.task import Task, TaskAttempt
from app.models.user import User, UserRole


class TeacherService:
    """Бизнес-логика учительского кабинета"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_student_for_teacher(
        self, teacher: User, student_id: UUID
    ) -> User:
        """Ученик, доступный учителю.

        Ученик должен состоять хотя бы в одном классе, которым владеет
        учитель; иначе 403 (чужая запись). Несуществующий ученик — 404,
        чтобы не раскрывать лишнего. Администратор не ограничен классами.
        """
        student = await self.db.get(User, student_id)
        if student is None or student.role != UserRole.STUDENT:
            raise NotFoundError("Ученик не найден")
        if teacher.role == UserRole.ADMIN:
            return student

        membership = (
            await self.db.execute(
                select(ClassroomMember.id)
                .join(Classroom, Classroom.id == ClassroomMember.classroom_id)
                .where(
                    Classroom.owner_id == teacher.id,
                    ClassroomMember.user_id == student.id,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if membership is None:
            raise AccessDeniedError("Ученик не состоит в ваших классах")
        return student

    async def list_attempts(
        self,
        teacher: User,
        student_id: UUID,
        *,
        task_id: UUID | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[tuple[TaskAttempt, str]], int]:
        """Попытки ученика с названием задачи, новые сверху"""
        student = await self.get_student_for_teacher(teacher, student_id)

        conditions = [TaskAttempt.user_id == student.id]
        if task_id is not None:
            conditions.append(TaskAttempt.task_id == task_id)

        total = int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(TaskAttempt)
                    .where(*conditions)
                )
            ).scalar_one()
        )
        result = await self.db.execute(
            select(TaskAttempt, Task.title)
            .join(Task, Task.id == TaskAttempt.task_id)
            .where(*conditions)
            .order_by(TaskAttempt.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return [(attempt, title) for attempt, title in result.all()], total

    async def get_attempt(
        self, teacher: User, student_id: UUID, attempt_id: UUID
    ) -> tuple[TaskAttempt, str]:
        """Попытка ученика с названием задачи.

        Попытка обязана принадлежать именно этому ученику: чужой
        идентификатор — 404, как и в ученическом API.
        """
        student = await self.get_student_for_teacher(teacher, student_id)
        result = await self.db.execute(
            select(TaskAttempt, Task.title)
            .join(Task, Task.id == TaskAttempt.task_id)
            .where(
                TaskAttempt.id == attempt_id,
                TaskAttempt.user_id == student.id,
            )
        )
        row = result.one_or_none()
        if row is None:
            raise NotFoundError("Попытка не найдена")
        return row[0], row[1]
