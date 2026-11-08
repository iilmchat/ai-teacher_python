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
from app.models.engagement import Notification
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

    async def add_members_bulk(
        self, classroom_id: UUID, actor: User, usernames: list[str]
    ) -> tuple[list[str], list[str], list[str]]:
        """Добавить учеников списком логинов (S46-005).

        Существующие участники и дубликаты — `skipped`, неизвестные логины —
        `unknown`; один запрос не ломается из-за части ошибок. Возвращает
        (added, skipped, unknown) в порядке входного списка.
        """
        classroom = await self._get_or_404(classroom_id)
        if classroom.owner_id != actor.id:
            raise AccessDeniedError(
                "Добавлять участников может только владелец"
            )
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in usernames:
            name = raw.strip()
            if not name or name in seen:
                continue
            seen.add(name)
            normalized.append(name)
        if not normalized:
            raise ValidationError("Укажите хотя бы один логин")

        users = {
            user.username: user
            for user in (
                await self.db.execute(
                    select(User).where(User.username.in_(normalized))
                )
            )
            .scalars()
            .all()
        }
        existing_ids = {
            member.user_id
            for member in await self.get_members(classroom_id)
        }
        added: list[str] = []
        skipped: list[str] = []
        unknown: list[str] = []
        for name in normalized:
            user = users.get(name)
            if user is None:
                unknown.append(name)
            elif user.id in existing_ids:
                skipped.append(name)
            else:
                self.db.add(
                    ClassroomMember(
                        classroom_id=classroom_id,
                        user_id=user.id,
                        role=ClassroomRole.STUDENT.value,
                    )
                )
                existing_ids.add(user.id)
                added.append(name)
        if added:
            await self.db.commit()
        return added, skipped, unknown

    async def remove_members_bulk(
        self, classroom_id: UUID, actor: User, user_ids: list[UUID]
    ) -> tuple[list[UUID], list[UUID]]:
        """Снять выбранных учеников (S46-005).

        Владелец и не-участники попадают в `skipped`; повторное снятие
        идемпотентно.
        """
        classroom = await self._get_or_404(classroom_id)
        if classroom.owner_id != actor.id:
            raise AccessDeniedError("Удалять участников может только владелец")
        member_ids = {
            member.user_id
            for member in await self.get_members(classroom_id)
        }
        removed: list[UUID] = []
        skipped: list[UUID] = []
        for user_id in user_ids:
            if user_id in member_ids and user_id != classroom.owner_id:
                removed.append(user_id)
            else:
                skipped.append(user_id)
        if removed:
            await self.db.execute(
                delete(ClassroomMember).where(
                    ClassroomMember.classroom_id == classroom_id,
                    ClassroomMember.user_id.in_(removed),
                )
            )
            await self.db.commit()
        return removed, skipped

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

    async def update_assignment(
        self,
        classroom_id: UUID,
        assignment_id: UUID,
        actor: User,
        due_at: datetime | None,
    ) -> tuple[Assignment, Task]:
        """Перенести срок назначения (S46-004).

        Меняется только `due_at`; прогресс учеников и уведомления о
        назначении остаются как есть.
        """
        classroom = await self._get_or_404(classroom_id)
        if classroom.owner_id != actor.id:
            raise AccessDeniedError("Менять назначения может только владелец")
        row = (
            await self.db.execute(
                select(Assignment, Task)
                .join(Task, Task.id == Assignment.task_id)
                .where(
                    Assignment.id == assignment_id,
                    Assignment.classroom_id == classroom_id,
                )
            )
        ).one_or_none()
        if row is None:
            raise NotFoundError("Назначение не найдено")
        assignment, task = row
        assignment.due_at = due_at
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment, task

    async def delete_assignment(
        self, classroom_id: UUID, assignment_id: UUID, actor: User
    ) -> bool:
        """Снять назначение (S46-004).

        Прогресс учеников сохраняется, а уведомления о назначении удаляются.
        Повторное снятие — не ошибка (идемпотентность): возвращается `False`.
        """
        classroom = await self._get_or_404(classroom_id)
        if classroom.owner_id != actor.id:
            raise AccessDeniedError("Снимать назначения может только владелец")
        assignment = await self.db.get(Assignment, assignment_id)
        if assignment is None or assignment.classroom_id != classroom_id:
            return False

        notifications = (
            await self.db.execute(
                select(Notification).where(Notification.type == "assignment")
            )
        ).scalars().all()
        stale_ids = [
            notification.id
            for notification in notifications
            if str(notification.payload.get("assignment_id")) == str(assignment_id)
        ]
        if stale_ids:
            await self.db.execute(
                delete(Notification).where(Notification.id.in_(stale_ids))
            )
        await self.db.delete(assignment)
        await self.db.commit()
        return True

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

    async def assignment_analytics(
        self,
        classroom_id: UUID,
        assignment_id: UUID,
        actor: User,
        *,
        problem_threshold: int = 3,
    ) -> AssignmentAnalyticsData:
        """Drill-down по одному назначению (S46-003).

        Агрегаты совпадают с матрицей прогресса класса: те же ученики, та же
        запись `UserTaskProgress`. «Просрочили» — дедлайн прошёл, а задача не
        завершена. «Проблемные» — ученики, сделавшие больше `problem_threshold`
        попыток.
        """
        classroom = await self._get_or_404(classroom_id)
        if classroom.owner_id != actor.id:
            raise AccessDeniedError(
                "Аналитику назначения видит только владелец"
            )
        row = (
            await self.db.execute(
                select(Assignment, Task)
                .join(Task, Task.id == Assignment.task_id)
                .where(
                    Assignment.id == assignment_id,
                    Assignment.classroom_id == classroom_id,
                )
            )
        ).one_or_none()
        if row is None:
            raise NotFoundError("Назначение не найдено")
        assignment, task = row

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
                await self.db.execute(
                    select(User).where(User.id.in_(student_ids))
                )
            )
            .scalars()
            .all()
        } if student_ids else {}

        progress_map: dict[UUID, UserTaskProgress] = {}
        if student_ids:
            progress_rows = (
                await self.db.execute(
                    select(UserTaskProgress).where(
                        UserTaskProgress.user_id.in_(student_ids),
                        UserTaskProgress.task_id == task.id,
                    )
                )
            ).scalars().all()
            progress_map = {record.user_id: record for record in progress_rows}

        now = datetime.utcnow()
        items: list[AssignmentAnalyticsStudentData] = []
        completed = in_progress = not_started = overdue = 0
        attempts_total = 0
        distribution: dict[int, int] = {}
        for member in students:
            record = progress_map.get(member.user_id)
            status_value = record.status if record else TaskStatus.NOT_STARTED
            attempts = record.attempts if record else 0
            is_overdue = bool(
                assignment.due_at is not None
                and assignment.due_at < now
                and status_value != TaskStatus.COMPLETED
            )
            if status_value == TaskStatus.COMPLETED:
                completed += 1
            elif status_value == TaskStatus.IN_PROGRESS:
                in_progress += 1
            else:
                not_started += 1
            if is_overdue:
                overdue += 1
            attempts_total += attempts
            distribution[attempts] = distribution.get(attempts, 0) + 1
            user = users.get(member.user_id)
            items.append(
                AssignmentAnalyticsStudentData(
                    student_id=member.user_id,
                    username=user.username if user is not None else "",
                    status=status_value,
                    attempts=attempts,
                    completed_at=record.completed_at if record else None,
                    overdue=is_overdue,
                )
            )

        problem_students = [
            item for item in items if item.attempts > problem_threshold
        ]
        return AssignmentAnalyticsData(
            assignment_id=assignment.id,
            task_id=task.id,
            task_title=task.title,
            due_at=assignment.due_at,
            total_students=len(students),
            completed=completed,
            in_progress=in_progress,
            not_started=not_started,
            overdue=overdue,
            attempts_total=attempts_total,
            attempts_distribution=[
                AssignmentAttemptBucketData(attempts=attempts, students=count)
                for attempts, count in sorted(distribution.items())
            ],
            problem_threshold=problem_threshold,
            problem_students=problem_students,
            students=items,
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
        from app.services.notification_prefs import notification_preferences

        if not settings.notifications_email_enabled or not student_ids:
            return
        # S45-004: письмо приходит только тем, кто включил e-mail-уведомления
        rows = (
            await self.db.execute(
                select(User.email, User.settings).where(User.id.in_(student_ids))
            )
        ).all()
        emails = [
            email
            for email, user_settings in rows
            if notification_preferences(user_settings)["email_notifications"]
        ]
        if not emails:
            return
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


@dataclass(slots=True)
class AssignmentAnalyticsStudentData:
    student_id: UUID
    username: str
    status: TaskStatus
    attempts: int
    completed_at: datetime | None
    overdue: bool


@dataclass(slots=True)
class AssignmentAttemptBucketData:
    attempts: int
    students: int


@dataclass(slots=True)
class AssignmentAnalyticsData:
    assignment_id: UUID
    task_id: UUID
    task_title: str
    due_at: datetime | None
    total_students: int
    completed: int
    in_progress: int
    not_started: int
    overdue: int
    attempts_total: int
    attempts_distribution: list[AssignmentAttemptBucketData]
    problem_threshold: int
    problem_students: list[AssignmentAnalyticsStudentData]
    students: list[AssignmentAnalyticsStudentData]
