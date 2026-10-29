"""
Teacher API (S15): список учеников, их прогресс и все задачи.

Доступ — `teacher` и `admin`. Ученик получает 403 на любом маршруте.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_role
from app.db.database import get_db
from app.db.repositories.task import ProgressRepository, TaskRepository
from app.models.task import Task, TaskStatus, UserTaskProgress
from app.models.user import User, UserRole
from app.schemas.task import TaskAdminDetail, TestCase
from app.schemas.teacher import (
    TeacherProgressItem,
    TeacherStudentDetail,
    TeacherStudentItem,
    TeacherStudentList,
    TeacherTaskItem,
    TeacherTaskList,
)

router = APIRouter(prefix="/teacher", tags=["Teacher"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
TeacherUser = Annotated[
    User, Depends(require_role(UserRole.TEACHER, UserRole.ADMIN))
]


def _student_item(
    user: User, completed: int, attempts: int
) -> TeacherStudentItem:
    return TeacherStudentItem(
        id=user.id,
        email=user.email,
        username=user.username,
        level=user.level,
        completed_tasks=int(completed),
        attempts=int(attempts),
        last_active=user.last_active,
    )


@router.get("/students", response_model=TeacherStudentList)
async def list_students(
    _: TeacherUser,
    db: DbSession,
    search: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> TeacherStudentList:
    """Ученики с числом решённых задач и попыток"""
    completed = func.count(UserTaskProgress.id).filter(
        UserTaskProgress.status == TaskStatus.COMPLETED
    )
    attempts = func.coalesce(func.sum(UserTaskProgress.attempts), 0)

    conditions = [User.role == UserRole.STUDENT]
    if search:
        pattern = f"%{search.strip().lower()}%"
        conditions.append(
            or_(
                func.lower(User.username).like(pattern),
                func.lower(User.email).like(pattern),
            )
        )

    total = int(
        (
            await db.execute(
                select(func.count()).select_from(User).where(*conditions)
            )
        ).scalar_one()
    )
    result = await db.execute(
        select(User, completed, attempts)
        .outerjoin(UserTaskProgress, UserTaskProgress.user_id == User.id)
        .where(*conditions)
        .group_by(User.id)
        .order_by(User.last_active.desc())
        .offset(skip)
        .limit(limit)
    )
    items = [
        _student_item(user, int(done or 0), int(tries or 0))
        for user, done, tries in result.all()
    ]
    return TeacherStudentList(total=total, items=items)


@router.get(
    "/students/{student_id}/progress", response_model=TeacherStudentDetail
)
async def student_progress(
    student_id: UUID, _: TeacherUser, db: DbSession
) -> TeacherStudentDetail:
    """Детальный прогресс ученика по задачам"""
    student = await db.get(User, student_id)
    if student is None or student.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ученик не найден"
        )

    tasks = await TaskRepository(db).list_tasks(limit=1000)
    progress = await ProgressRepository(db).get_user_progress_map(student.id)

    items: list[TeacherProgressItem] = []
    completed = in_progress = 0
    attempts = 0
    for task in tasks:
        record = progress.get(task.id)
        status_value = record.status if record else TaskStatus.NOT_STARTED
        if status_value == TaskStatus.COMPLETED:
            completed += 1
        elif status_value == TaskStatus.IN_PROGRESS:
            in_progress += 1
        attempts += record.attempts if record else 0
        items.append(
            TeacherProgressItem(
                task_id=task.id,
                title=task.title,
                difficulty=task.difficulty,
                status=status_value,
                attempts=record.attempts if record else 0,
                completed_at=record.completed_at if record else None,
            )
        )

    total = len(tasks)
    return TeacherStudentDetail(
        student=_student_item(student, completed, attempts),
        total_tasks=total,
        completed=completed,
        in_progress=in_progress,
        completion_rate=round(completed / total * 100, 1) if total else 0.0,
        items=items,
    )


@router.get("/tasks", response_model=TeacherTaskList)
async def list_all_tasks(_: TeacherUser, db: DbSession) -> TeacherTaskList:
    """Все задачи, включая деактивированные"""
    tasks = await TaskRepository(db).list_tasks(only_active=False, limit=1000)
    items = [
        TeacherTaskItem(
            id=task.id,
            title=task.title,
            difficulty=task.difficulty,
            category=task.category,
            tags=list(task.tags or []),
            test_cases_count=len(task.test_cases or []),
            hints_count=len(task.hints or []),
            is_active=task.is_active,
            created_at=task.created_at,
        )
        for task in tasks
    ]
    return TeacherTaskList(total=len(items), items=items)


@router.get("/tasks/{task_id}", response_model=TaskAdminDetail)
async def get_task_for_teacher(
    task_id: UUID, _: TeacherUser, db: DbSession
) -> TaskAdminDetail:
    """Полная карточка задачи (с тест-кейсами) для редактирования"""
    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена"
        )
    return TaskAdminDetail(
        id=task.id,
        title=task.title,
        description=task.description,
        difficulty=task.difficulty,
        category=task.category,
        tags=list(task.tags or []),
        hints=list(task.hints or []),
        solution_template=task.solution_template,
        test_cases_count=len(task.test_cases or []),
        status=TaskStatus.NOT_STARTED,
        attempts=0,
        test_cases=[TestCase(**case) for case in (task.test_cases or [])],
        is_active=task.is_active,
    )
