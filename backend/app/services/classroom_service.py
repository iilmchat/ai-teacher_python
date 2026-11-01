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
from app.models.classroom import (
    Assignment,
    AssignmentTemplate,
    Classroom,
    ClassroomMember,
    ClassroomRole,
)
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

    async def list_for_user_with_counts(
        self, user: User, skip: int = 0, limit: int = 100
    ) -> list[tuple[Classroom, int]]:
        """Классы пользователя вместе с числом участников.

        S19-004: вместо N+1 (`members_count` на каждый класс) — один запрос
        с `GROUP BY`: число участников считается на стороне БД.
        """
        member_count = func.count(ClassroomMember.id)
        user_classrooms = select(ClassroomMember.classroom_id).where(
            ClassroomMember.user_id == user.id
        )
        result = await self.db.execute(
            select(Classroom, member_count)
            .join(ClassroomMember, ClassroomMember.classroom_id == Classroom.id)
            .where(Classroom.id.in_(user_classrooms))
            .group_by(Classroom.id)
            .order_by(Classroom.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return [(row[0], int(row[1])) for row in result.all()]

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
        """Назначения класса со счётчиками выполнения.

        S19-004: счётчики «выполнили» считаются одним агрегирующим запросом
        по всем назначениям, а не отдельным запросом на каждое.
        """
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
        rows = result.all()
        completed_by_task: dict[UUID, int] = {}
        if student_ids and rows:
            counts = await self.db.execute(
                select(UserTaskProgress.task_id, func.count())
                .where(
                    UserTaskProgress.task_id.in_(
                        [assignment.task_id for assignment, _ in rows]
                    ),
                    UserTaskProgress.user_id.in_(student_ids),
                    UserTaskProgress.status == TaskStatus.COMPLETED,
                )
                .group_by(UserTaskProgress.task_id)
            )
            completed_by_task = {
                task_id: int(count) for task_id, count in counts.all()
            }

        return [
            AssignmentItemData(
                assignment=assignment,
                task=task,
                completed_count=completed_by_task.get(task.id, 0),
                total_members=total_members,
            )
            for assignment, task in rows
        ]

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


    # --- Массовые назначения, шаблоны и журнал (S28) -------------------

    async def add_assignments_bulk(
        self,
        classroom_id: UUID,
        actor: User,
        task_ids: list[UUID],
        due_at: datetime | None,
    ) -> tuple[list[UUID], list[UUID], list[UUID]]:
        """Идемпотентно назначить набор задач: (created, skipped, unknown).

        Дубликаты и уже назначенные задачи попадают в `skipped`, неактивные и
        несуществующие — в `unknown`; ни одна из них не ломает запрос.
        """
        classroom = await self._get_or_404(classroom_id)
        if classroom.owner_id != actor.id:
            raise AccessDeniedError("Назначать задачи может только владелец")

        unique_ids = list(dict.fromkeys(task_ids))
        duplicates = {
            task_id for task_id in unique_ids if task_ids.count(task_id) > 1
        }
        tasks = (
            await self.db.execute(select(Task).where(Task.id.in_(unique_ids)))
        ).scalars().all()
        active = {task.id: task for task in tasks if task.is_active}
        existing = set(
            (
                await self.db.execute(
                    select(Assignment.task_id).where(
                        Assignment.classroom_id == classroom_id,
                        Assignment.task_id.in_(unique_ids),
                    )
                )
            ).scalars().all()
        )

        created: list[UUID] = []
        skipped: list[UUID] = []
        unknown: list[UUID] = []
        new_assignments: list[tuple[Assignment, Task]] = []
        for task_id in unique_ids:
            if task_id in existing:
                skipped.append(task_id)
                continue
            task = active.get(task_id)
            if task is None:
                unknown.append(task_id)
                continue
            assignment = Assignment(
                classroom_id=classroom_id, task_id=task_id, due_at=due_at
            )
            self.db.add(assignment)
            new_assignments.append((assignment, task))
            created.append(task_id)
        for duplicate in duplicates:
            if duplicate not in skipped:
                skipped.append(duplicate)
        await self.db.commit()

        if not new_assignments:
            return created, skipped, unknown

        for assignment, _ in new_assignments:
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

            for assignment, task in new_assignments:
                await create_assignment_notifications(
                    self.db,
                    student_ids,
                    classroom_id=classroom.id,
                    classroom_name=classroom.name,
                    assignment_id=assignment.id,
                    task_title=task.title,
                    due_at=due_at,
                )
            await self._send_assignment_emails(
                classroom, student_ids, [task for _, task in new_assignments], due_at
            )
        return created, skipped, unknown

    async def _send_assignment_emails(
        self,
        classroom: Classroom,
        student_ids: list[UUID],
        tasks: list[Task],
        due_at: datetime | None,
    ) -> None:
        """Best-effort email-уведомления (S28-004): SMTP-сбой не ломает API"""
        from app.config import settings
        from app.services.email import get_email_sender, send_assignment_email

        if not settings.notifications_email_enabled or not student_ids:
            return
        emails = (
            await self.db.execute(
                select(User.email).where(User.id.in_(student_ids))
            )
        ).scalars().all()
        sender = get_email_sender()
        due = due_at.isoformat() if due_at else None
        for task in tasks:
            for email in emails:
                await send_assignment_email(
                    sender,
                    to=email,
                    classroom_name=classroom.name,
                    task_title=task.title,
                    due_at=due,
                )

    async def create_template(
        self, owner: User, name: str, task_ids: list[UUID]
    ) -> AssignmentTemplate:
        """Создать шаблон назначений учителя (S28-002)"""
        from app.models.user import UserRole

        if owner.role not in (UserRole.TEACHER, UserRole.ADMIN):
            raise AccessDeniedError("Шаблоны доступны преподавателю")
        unique = list(dict.fromkeys(task_ids))
        if not unique:
            raise ValidationError("Шаблон должен содержать хотя бы одну задачу")
        template = AssignmentTemplate(
            owner_id=owner.id, name=name, task_ids=[str(task_id) for task_id in unique]
        )
        self.db.add(template)
        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def list_templates(self, owner: User) -> list[AssignmentTemplate]:
        """Шаблоны текущего учителя, новые сверху"""
        rows = (
            await self.db.execute(
                select(AssignmentTemplate)
                .where(AssignmentTemplate.owner_id == owner.id)
                .order_by(AssignmentTemplate.created_at.desc())
            )
        ).scalars().all()
        return list(rows)

    async def delete_template(self, template_id: UUID, owner: User) -> bool:
        """Удалить свой шаблон (404/403 через None)"""
        template = await self.db.get(AssignmentTemplate, template_id)
        if template is None:
            raise NotFoundError("Шаблон не найден")
        if template.owner_id != owner.id:
            raise AccessDeniedError("Можно удалить только свой шаблон")
        await self.db.delete(template)
        await self.db.commit()
        return True

    async def apply_template(
        self,
        classroom_id: UUID,
        actor: User,
        template_id: UUID,
        due_at: datetime | None,
    ) -> tuple[list[UUID], list[UUID], list[UUID]]:
        """Применить шаблон к классу (массовое назначение)"""
        template = await self.db.get(AssignmentTemplate, template_id)
        if template is None:
            raise NotFoundError("Шаблон не найден")
        if template.owner_id != actor.id:
            raise AccessDeniedError("Можно применить только свой шаблон")
        task_ids = [UUID(str(value)) for value in (template.task_ids or [])]
        return await self.add_assignments_bulk(
            classroom_id, actor, task_ids, due_at
        )

    async def class_gradebook(self, classroom_id: UUID, actor: User) -> GradebookData:
        """Журнал оценок: ячейки с completed_at и числом просрочек (S28-003)"""
        progress = await self.class_progress(classroom_id, actor)
        member_ids = [student.id for student in progress.students]
        task_ids = [task.id for task in progress.tasks]
        rows = []
        if member_ids and task_ids:
            rows = list(
                (
                    await self.db.execute(
                        select(UserTaskProgress).where(
                            UserTaskProgress.user_id.in_(member_ids),
                            UserTaskProgress.task_id.in_(task_ids),
                        )
                    )
                ).scalars().all()
            )
        completed_at_map = {
            (row.user_id, row.task_id): row.completed_at for row in rows
        }

        due_rows = (
            await self.db.execute(
                select(Assignment.task_id, Assignment.due_at).where(
                    Assignment.classroom_id == classroom_id
                )
            )
        ).all()
        due_by_task: dict[UUID, datetime | None] = {}
        for due_task_id, due_at_value in due_rows:
            due_by_task[due_task_id] = due_at_value

        now = datetime.utcnow()
        cells = []
        overdue = 0
        for cell in progress.cells:
            due_at = due_by_task.get(cell.task_id)
            completed = completed_at_map.get((cell.student_id, cell.task_id))
            if (
                due_at is not None
                and due_at < now
                and cell.status != TaskStatus.COMPLETED
            ):
                overdue += 1
            cells.append(
                GradebookCellData(
                    student_id=cell.student_id,
                    task_id=cell.task_id,
                    status=cell.status,
                    attempts=cell.attempts,
                    completed_at=completed,
                )
            )
        return GradebookData(
            students=progress.students,
            tasks=progress.tasks,
            cells=cells,
            completion_rate=progress.completion_rate,
            overdue=overdue,
        )

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


@dataclass(slots=True)
class GradebookCellData:
    student_id: UUID
    task_id: UUID
    status: TaskStatus
    attempts: int
    completed_at: datetime | None


@dataclass(slots=True)
class GradebookData:
    students: list[ProgressStudentData]
    tasks: list[ProgressTaskData]
    cells: list[GradebookCellData]
    completion_rate: float
    overdue: int
