"""
Task API: список задач, проверка решений, прогресс (S7-005, S7-006).

Статические маршруты (`/progress`, `/stats`) объявлены раньше
`/{task_id}`, иначе FastAPI пытается разобрать слово как UUID.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.executor import SandboxedExecutor
from app.core.security import get_current_active_user, require_role
from app.db.database import get_db
from app.models.task import Task, TaskDifficulty
from app.models.user import User, UserRole
from app.schemas.task import (
    HintResponse,
    ProgressSummary,
    SubmitRequest,
    SubmitResponse,
    TaskAdminDetail,
    TaskCreate,
    TaskDetail,
    TaskListItem,
    TaskStatsResponse,
    TaskUpdate,
    TestCase,
)
from app.services.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_active_user)]
TeacherUser = Annotated[
    User, Depends(require_role(UserRole.TEACHER, UserRole.ADMIN))
]


def get_executor() -> SandboxedExecutor:
    """Песочница для проверки решений"""
    return SandboxedExecutor(timeout=float(settings.executor_timeout))


def get_task_service(
    db: DbSession,
    executor: Annotated[SandboxedExecutor, Depends(get_executor)],
) -> TaskService:
    """Сервис задач"""
    return TaskService(db, executor)


TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]


@router.get("", response_model=list[TaskListItem])
async def list_tasks(
    current_user: CurrentUser,
    service: TaskServiceDep,
    difficulty: TaskDifficulty | None = None,
    category: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[TaskListItem]:
    """Каталог задач с фильтрами и статусом прохождения"""
    return await service.list_tasks(
        current_user,
        difficulty=difficulty,
        category=category,
        skip=skip,
        limit=limit,
    )


@router.get("/progress", response_model=ProgressSummary)
async def get_progress(
    current_user: CurrentUser, service: TaskServiceDep
) -> ProgressSummary:
    """Сводка прогресса ученика"""
    return await service.get_progress(current_user)


@router.get("/stats", response_model=TaskStatsResponse)
async def get_stats(
    current_user: CurrentUser, service: TaskServiceDep
) -> TaskStatsResponse:
    """Статистика задач и активности"""
    return await service.get_stats(current_user)


@router.get("/{task_id}", response_model=TaskDetail)
async def get_task(
    task_id: UUID, current_user: CurrentUser, service: TaskServiceDep
) -> TaskDetail:
    """Карточка задачи"""
    return await service.get_task_detail(task_id, current_user)


@router.get("/{task_id}/hints/{index}", response_model=HintResponse)
async def get_hint(
    task_id: UUID, index: int, service: TaskServiceDep
) -> HintResponse:
    """Подсказка по номеру (с нуля)"""
    hint, total = await service.get_hint(task_id, index)
    return HintResponse(index=index, hint=hint, total=total)


@router.post("/{task_id}/submit", response_model=SubmitResponse)
async def submit_solution(
    task_id: UUID,
    payload: SubmitRequest,
    current_user: CurrentUser,
    service: TaskServiceDep,
) -> SubmitResponse:
    """Проверить решение по тест-кейсам"""
    return await service.submit_solution(task_id, current_user, payload.code)


# --- Управление задачами (преподаватель/админ) --------------------------


@router.post("", response_model=TaskAdminDetail, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    author: TeacherUser,
    service: TaskServiceDep,
) -> TaskAdminDetail:
    """Создать задачу (только преподаватель или админ)"""
    task: Task = await service.create_task(payload, author)
    return _admin_detail(task)


@router.patch("/{task_id}", response_model=TaskAdminDetail)
async def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    _: TeacherUser,
    service: TaskServiceDep,
) -> TaskAdminDetail:
    """Обновить задачу"""
    task = await service.update_task(task_id, payload)
    return _admin_detail(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    _: TeacherUser,
    service: TaskServiceDep,
) -> None:
    """Удалить или деактивировать задачу"""
    await service.delete_task(task_id)


def _admin_detail(task: Task) -> TaskAdminDetail:
    """Собрать ответ для преподавателя"""
    from app.models.task import TaskStatus

    return TaskAdminDetail(
        id=task.id,
        title=task.title,
        description=task.description,
        difficulty=task.difficulty,
        category=task.category,
        hints=list(task.hints or []),
        solution_template=task.solution_template,
        test_cases_count=len(task.test_cases or []),
        status=TaskStatus.NOT_STARTED,
        attempts=0,
        test_cases=[TestCase(**case) for case in (task.test_cases or [])],
        is_active=task.is_active,
    )
