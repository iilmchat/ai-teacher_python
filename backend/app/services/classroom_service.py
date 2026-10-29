"""
Сервис классов и назначений (S16-002…S16-004).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errors import AccessDeniedError, ConflictError, NotFoundError, ValidationError
from app.models.classroom import Assignment, Classroom, ClassroomMember, ClassroomRole
from app.models.task import Task, TaskStatus, UserTaskProgress
from app.models.user import User

JOIN_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
JOIN_CODE_LENGTH = 6


class ClassroomService:
    """Бизнес-логика классов"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # --- Классы ---------------------------------------------------------

    async def _generate_join_code(self) -> str:
        for _ in range(10):
            code = "".join(
                secrets.choice(JOIN_CODE_ALPHABET)
                for _ in range(JOIN_CODE_LENGTH)
            )
            exists = await self.db.execute(
                select(Classroom.id).where(Classroom.join_code == code)
            )
            if exists.scalar_one_or_none() is None:
                return code
        raise ConflictError("Не удалось сгенерировать код класса")

    async def create_classroom(self, owner: User, name: str) -> Classroom:
        """Создать класс; владелец сразу становится участником-owner"""
        classroom = Classroom(
            name=name.strip(),
            owner_id=owner.id,
            join_code=await self._generate_join_code(),
        )
        self.db.add(classroom)
        await self.db.flush()
        self.db.add(
            ClassroomMember(
                classroom_id=classroom.id,
                user_id=owner.id,
                role=ClassroomRole.OWNER.value,
            )
        )
        await self.db.commit()
        await self.db.refresh(classroom)
        return classroom

    async def list_for_user(self, user: User) -> list[Classroom]:
        """Классы, где пользователь — участник (владелец тоже участник)"""
        result = await self.db.execute(
            select(Classroom)
            .join(ClassroomMember, ClassroomMember.classroom_id == Classroom.id)
            .where(ClassroomMember.user_id == user.id)
            .order_by(Classroom.created_at.desc())
        )
        return list(result.scalars().all())

    async def members_count(self, classroom_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(ClassroomMember)
            .where(ClassroomMember.classroom_id == classroom_id)
        )
        return int(result.scalar_one())

    async def _membership(
        self, classroom_id: UUID, user_id: UUID
    ) -> ClassroomMember | None:
        result = await self.db.execute(
            select(ClassroomMember).where(
                ClassroomMember.classroom_id == classroom_id,
                ClassroomMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_or_404(self, classroom_id: UUID) -> Classroom:
        classroom = await self.db.get(Classroom, classroom_id)
        if classroom is None:
            raise NotFoundError("Класс не найден")
        return classroom

    async def get_for_user(
        self, classroom_id: UUID, user: User, with_members: bool = False
    ) -> Classroom:
        """Класс с проверкой членства"""
        query = select(Classroom).where(Classroom.id == classroom_id)
        if with_members:
            query = query.options(selectinload(Classroom.members))
        result = await self.db.execute(query)
        classroom = result.scalar_one_or_none()
        if classroom is None:
            raise NotFoundError("Класс не найден")
        if await self._membership(classroom_id, user.id) is None:
            raise AccessDeniedError("Вы не участник этого класса")
        return classroom

    async def get_members(self, classroom_id: UUID) -> list[ClassroomMember]:
        result = await self.db.execute(
            select(ClassroomMember)
            .where(ClassroomMember.classroom_id == classroom_id)
            .order_by(ClassroomMember.joined_at.asc())
        )
        return list(result.scalars().all())

    async def join_by_code(self, user: User, code: str) -> Classroom:
        """Вступить в класс по коду (идемпотентно)"""
        normalized = code.strip().upper()
        result = await self.db.execute(
            select(Classroom).where(Classroom.join_code == normalized)
        )
        classroom = result.scalar_one_or_none()
        if classroom is None:
            raise NotFoundError("Класс с таким кодом не найден")
        if await self._membership(classroom.id, user.id) is None:
            self.db.add(
                ClassroomMember(
                    classroom_id=classroom.id,
                    user_id=user.id,
                    role=ClassroomRole.STUDENT.value,
                )
            )
            await self.db.commit()
        return classroom

    async def remove_member(
        self, classroom_id: UUID, member_id: UUID, actor: User
    ) -> None:
        """Удалить участника (только владелец, кроме себя)"""
        classroom = await self._get_or_404(classroom_id)
        if classroom.owner_id != actor.id:
            raise AccessDeniedError("Удалять участников может только владелец")
        if member_id == classroom.owner_id:
            raise ValidationError("Нельзя удалить владельца класса")
        await self.db.execute(
            delete(ClassroomMember).where(
                ClassroomMember.classroom_id == classroom_id,
                ClassroomMember.user_id == member_id,
            )
        )
        await self.db.commit()

    # --- Назначения -----------------------------------------------------

    async def add_assignment(
        self,
        classroom_id: UUID,
        actor: User,
        task_id: UUID,
        due_at: datetime | None,
    ) -> Assignment:
        """Назначить задачу классу (только владелец)"""
        classroom = await self._get_or_404(classroom_id)
        if classroom.owner_id != actor.id:
            raise AccessDeniedError("Назначать задачи может только владелец")
        task = await self.db.get(Task, task_id)
        if task is None or not task.is_active:
            raise NotFoundError("Задача не найдена")

        existing = await self.db.execute(
            select(Assignment).where(
                Assignment.classroom_id == classroom_id,
                Assignment.task_id == task_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("Эта задача уже назначена классу")

        assignment = Assignment(
            classroom_id=classroom_id, task_id=task_id, due_at=due_at
        )
        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)

        members = await self.get_members(classroom_id)
        student_ids = [
            member.user_id
            for member in members
            if member.role == ClassroomRole.STUDENT.value
        ]
        if student_ids:
            from app.services.engagement_service import (
                create_assignment_notifications,
            )

            await create_assignment_notifications(
                self.db,
                student_ids,
                classroom_id=classroom.id,
                classroom_name=classroom.name,
                assignment_id=assignment.id,
                task_title=task.title,
                due_at=due_at,
            )
        return assignment

    async def list_assignments(
        self, classroom_id: UUID, user: User
    ) -> list[AssignmentItemData]:
        """Назначения класса со счётчиками выполнения"""
        await self.get_for_user(classroom_id, user)
        members = await self.get_members(classroom_id)
        student_ids = [
            member.user_id
            for member in members
            if member.role == ClassroomRole.STUDENT.value
        ]
        total_members = len(student_ids)

        result = await self.db.execute(
            select(Assignment, Task)
            .join(Task, Task.id == Assignment.task_id)
            .where(Assignment.classroom_id == classroom_id)
            .order_by(Assignment.created_at.desc())
        )
        items: list[AssignmentItemData] = []
        for assignment, task in result.all():
            completed = 0
            if student_ids:
                completed_result = await self.db.execute(
                    select(func.count())
                    .select_from(UserTaskProgress)
                    .where(
                        UserTaskProgress.task_id == task.id,
                        UserTaskProgress.user_id.in_(student_ids),
                        UserTaskProgress.status == TaskStatus.COMPLETED,
                    )
                )
                completed = int(completed_result.scalar_one())
            items.append(
                AssignmentItemData(
                    assignment=assignment,
                    task=task,
                    completed_count=completed,
                    total_members=total_members,
                )
            )
        return items

    async def my_assignments(self, user: User) -> list[MyAssignmentData]:
        """Задания пользователя по всем его классам"""
        result = await self.db.execute(
            select(Assignment, Task, Classroom)
            .join(Classroom, Classroom.id == Assignment.classroom_id)
            .join(Task, Task.id == Assignment.task_id)
            .join(
                ClassroomMember,
                (ClassroomMember.classroom_id == Classroom.id)
                & (ClassroomMember.user_id == user.id),
            )
            .order_by(Assignment.due_at.asc().nullslast())
        )
        progress_map = {
            item.task_id: item
            for item in (
                await self.db.execute(
                    select(UserTaskProgress).where(
                        UserTaskProgress.user_id == user.id
                    )
                )
            )
            .scalars()
            .all()
        }
        now = datetime.utcnow()
        items: list[MyAssignmentData] = []
        for assignment, task, classroom in result.all():
            record = progress_map.get(task.id)
            status_value = record.status if record else TaskStatus.NOT_STARTED
            overdue = bool(
                assignment.due_at
                and assignment.due_at < now
                and status_value != TaskStatus.COMPLETED
            )
            items.append(
                MyAssignmentData(
                    assignment=assignment,
                    task=task,
                    classroom=classroom,
                    status=status_value,
                    overdue=overdue,
                )
            )
        return items

    async def class_progress(
        self, classroom_id: UUID, actor: User
    ) -> ClassProgressData:
        """Матрица «ученик × задача» и агрегаты"""
        classroom = await self._get_or_404(classroom_id)
        if classroom.owner_id != actor.id:
            raise AccessDeniedError("Прогресс класса видит только владелец")
        members = await self.get_members(classroom_id)
        students = [
            member
            for member in members
            if member.role == ClassroomRole.STUDENT.value
        ]
        student_ids = [member.user_id for member in students]
        users = {
            user.id: user
            for user in (
                await self.db.execute(select(User).where(User.id.in_(student_ids)))
            )
            .scalars()
            .all()
        }

        assignment_rows = (
            await self.db.execute(
                select(Assignment, Task)
                .join(Task, Task.id == Assignment.task_id)
                .where(Assignment.classroom_id == classroom_id)
                .order_by(Assignment.created_at.asc())
            )
        ).all()
        tasks = [task for _, task in assignment_rows]

        progress_rows = []
        if tasks and student_ids:
            progress_rows = list(
                (
                    await self.db.execute(
                        select(UserTaskProgress).where(
                            UserTaskProgress.user_id.in_(student_ids),
                            UserTaskProgress.task_id.in_([task.id for task in tasks]),
                        )
                    )
                )
                .scalars()
                .all()
            )
        progress_map = {(row.user_id, row.task_id): row for row in progress_rows}

        cells: list[ProgressCellData] = []
        completed = 0
        attempts_by_task: dict[UUID, tuple[int, int]] = {}
        for task in tasks:
            attempts_by_task[task.id] = (0, 0)
        for student in students:
            username = users[student.user_id].username if student.user_id in users else ""
            for task in tasks:
                record = progress_map.get((student.user_id, task.id))
                status_value = record.status if record else TaskStatus.NOT_STARTED
                attempts = record.attempts if record else 0
                if status_value == TaskStatus.COMPLETED:
                    completed += 1
                task_attempts, task_completed = attempts_by_task[task.id]
                attempts_by_task[task.id] = (
                    task_attempts + attempts,
                    task_completed + (1 if status_value == TaskStatus.COMPLETED else 0),
                )
                cells.append(
                    ProgressCellData(
                        student_id=student.user_id,
                        student_name=username,
                        task_id=task.id,
                        status=status_value,
                        attempts=attempts,
                    )
                )

        total_cells = len(students) * len(tasks)
        problem_tasks = [
            ProblemTaskData(
                task_id=task.id,
                title=task.title,
                attempts=attempts_by_task[task.id][0],
                completed=attempts_by_task[task.id][1],
            )
            for task in tasks
            if len(students) > 0
            and attempts_by_task[task.id][1] < len(students)
            and attempts_by_task[task.id][0] >= len(students)
        ]

        return ClassProgressData(
            students=[
                ProgressStudentData(
                    id=student.user_id,
                    username=users[student.user_id].username
                    if student.user_id in users
                    else "",
                )
                for student in students
            ],
            tasks=[ProgressTaskData(id=task.id, title=task.title) for task in tasks],
            cells=cells,
            completion_rate=round(completed / total_cells * 100, 1)
            if total_cells
            else 0.0,
            problem_tasks=problem_tasks,
        )


# --- Внутренние dataclass-структуры (без Pydantic в сервисе) -------------


@dataclass(slots=True)
class AssignmentItemData:
    assignment: Assignment
    task: Task
    completed_count: int
    total_members: int


@dataclass(slots=True)
class MyAssignmentData:
    assignment: Assignment
    task: Task
    classroom: Classroom
    status: TaskStatus
    overdue: bool


@dataclass(slots=True)
class ProgressCellData:
    student_id: UUID
    student_name: str
    task_id: UUID
    status: TaskStatus
    attempts: int


@dataclass(slots=True)
class ProblemTaskData:
    task_id: UUID
    title: str
    attempts: int
    completed: int


@dataclass(slots=True)
class ProgressStudentData:
    id: UUID
    username: str


@dataclass(slots=True)
class ProgressTaskData:
    id: UUID
    title: str


@dataclass(slots=True)
class ClassProgressData:
    students: list[ProgressStudentData]
    tasks: list[ProgressTaskData]
    cells: list[ProgressCellData]
    completion_rate: float
    problem_tasks: list[ProblemTaskData]
