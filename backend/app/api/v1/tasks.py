"""
Task API: список задач, проверка решений, прогресс (S7-005, S7-006).

Статические маршруты (`/progress`, `/stats`) объявлены раньше
`/{task_id}`, иначе FastAPI пытается разобрать слово как UUID.
"""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.executor import SandboxedExecutor
from app.core.rate_limiter import CHECK_LIMIT, WINDOW_SECONDS, is_user_limited
from app.core.security import get_current_active_user, require_role
from app.db.database import get_db
from app.errors import ValidationError
from app.models.task import Task, TaskDifficulty
from app.models.user import User, UserRole
from app.schemas.task import (
    AttemptDetail,
    AttemptList,
    CategoriesResponse,
    CheckRequest,
    DraftRequest,
    DraftStatus,
    HintResponse,
    ProgressSummary,
    SubmitRequest,
    SubmitResponse,
    TaskAdminDetail,
    TaskCreate,
    TaskDetail,
    TaskGenerateRequest,
    TaskGenerateResponse,
    TaskImportContent,
    TaskImportPreview,
    TaskImportRequest,
    TaskImportResponse,
    TaskListItem,
    TaskStatsResponse,
    TaskUpdate,
    TaskVersionList,
    TestCase,
)
from app.services.audit_service import record_audit
from app.services.cache import (
    cache_get_json,
    cache_set_json,
    categories_cache_key,
    tasks_list_cache_key,
)
from app.services.llm import LLMProvider, create_llm_provider
from app.services.task_generation import generate_tasks
from app.services.task_import import (
    export_tasks,
    export_to_yaml,
    import_tasks,
    parse_task_payload,
    preview_import,
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
    tag: str | None = None,
    q: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[TaskListItem]:
    """Каталог задач с фильтрами и статусом прохождения (кэш S19-003)"""
    cache_key = tasks_list_cache_key(
        current_user.id,
        difficulty=difficulty.value if difficulty is not None else None,
        category=category,
        tag=tag,
        search=q,
        skip=skip,
        limit=limit,
    )
    cached = await cache_get_json(cache_key)
    if isinstance(cached, list):
        return [TaskListItem.model_validate(item) for item in cached]

    items = await service.list_tasks(
        current_user,
        difficulty=difficulty,
        category=category,
        tag=tag,
        search=q,
        skip=skip,
        limit=limit,
    )
    await cache_set_json(cache_key, [item.model_dump(mode="json") for item in items])
    return items


@router.get("/progress", response_model=ProgressSummary)
async def get_progress(
    current_user: CurrentUser, service: TaskServiceDep
) -> ProgressSummary:
    """Сводка прогресса ученика"""
    return await service.get_progress(current_user)


@router.get("/categories", response_model=CategoriesResponse)
async def list_categories(
    _: CurrentUser, service: TaskServiceDep
) -> CategoriesResponse:
    """Категории активных задач (S14-004, кэш S19-003)"""
    key = categories_cache_key()
    cached = await cache_get_json(key)
    if isinstance(cached, dict):
        return CategoriesResponse.model_validate(cached)

    response = CategoriesResponse(categories=await service.list_categories())
    await cache_set_json(key, response.model_dump(mode="json"))
    return response


@router.get("/export")
async def export_tasks_endpoint(
    _: TeacherUser,
    service: TaskServiceDep,
    format: Literal["json", "yaml"] = "json",
) -> Any:
    """Выгрузка всех активных задач в JSON или YAML (S14-001)"""
    tasks = await service.export_active()
    if format == "yaml":
        return Response(
            content=export_to_yaml(tasks), media_type="application/yaml"
        )
    return export_tasks(tasks)


@router.post("/import", response_model=TaskImportResponse)
async def import_tasks_endpoint(
    payload: TaskImportRequest,
    author: TeacherUser,
    db: DbSession,
) -> TaskImportResponse:
    """Импорт задач из JSON/YAML-представления (S14-001)"""
    return await import_tasks(db, payload.tasks, author)


@router.post("/import/preview", response_model=TaskImportPreview)
async def preview_import_endpoint(
    payload: TaskImportContent,
    _: TeacherUser,
) -> TaskImportPreview:
    """Предпросмотр файла перед импортом: задачи и ошибки (S15-003)"""
    try:
        return preview_import(payload.content)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc


@router.post("/import/file", response_model=TaskImportResponse)
async def import_tasks_file(
    file: UploadFile,
    author: TeacherUser,
    db: DbSession,
) -> TaskImportResponse:
    """Импорт задач из загруженного JSON/YAML-файла (S15-003)"""
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("Файл должен быть в кодировке UTF-8") from exc
    try:
        items = parse_task_payload(text)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    return await import_tasks(db, items, author)


def get_llm_provider() -> LLMProvider:
    """Провайдер LLM для генерации задач; переопределяется в тестах"""
    return create_llm_provider()


LLMProviderDep = Annotated[LLMProvider, Depends(get_llm_provider)]
ExecutorDep = Annotated[SandboxedExecutor, Depends(get_executor)]


@router.post("/generate", response_model=TaskGenerateResponse)
async def generate_tasks_endpoint(
    payload: TaskGenerateRequest,
    author: TeacherUser,
    service: TaskServiceDep,
    executor: ExecutorDep,
    provider: LLMProviderDep,
) -> TaskGenerateResponse:
    """Сгенерировать задачи через LLM и проверить эталон в песочнице (S14-003)"""
    try:
        accepted, rejected, usage = await generate_tasks(provider, payload, executor)
    finally:
        await provider.close()

    created = await service.create_many(accepted, author)
    return TaskGenerateResponse(
        created=[_admin_detail(task) for task in created],
        rejected=rejected,
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
    )


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
    task_id: UUID, index: int, _: CurrentUser, service: TaskServiceDep
) -> HintResponse:
    """Подсказка по номеру (с нуля).

    S20-003: подсказки доступны только аутентифицированным пользователям —
    как и остальные роуты `/tasks` (раньше эндпоинт был анонимным).
    """
    hint, total = await service.get_hint(task_id, index)
    return HintResponse(index=index, hint=hint, total=total)


@router.get("/{task_id}/versions", response_model=TaskVersionList)
async def list_task_versions(
    task_id: UUID, _: TeacherUser, service: TaskServiceDep
) -> TaskVersionList:
    """История версий задачи (S14-005)"""
    return TaskVersionList(items=await service.list_versions(task_id))


@router.post(
    "/{task_id}/versions/{version}/restore", response_model=TaskAdminDetail
)
async def restore_task_version(
    task_id: UUID,
    version: int,
    author: TeacherUser,
    service: TaskServiceDep,
) -> TaskAdminDetail:
    """Откатить задачу к выбранной версии"""
    task = await service.restore_version(task_id, version, author)
    return _admin_detail(task)


@router.post("/{task_id}/submit", response_model=SubmitResponse)
async def submit_solution(
    task_id: UUID,
    payload: SubmitRequest,
    current_user: CurrentUser,
    service: TaskServiceDep,
) -> SubmitResponse:
    """Проверить решение по тест-кейсам"""
    return await service.submit_solution(task_id, current_user, payload.code)


@router.post("/{task_id}/check", response_model=SubmitResponse)
async def check_solution(
    task_id: UUID,
    payload: CheckRequest,
    current_user: CurrentUser,
    service: TaskServiceDep,
) -> SubmitResponse:
    """Пробная проверка решения (S42-001).

    Отличается от `submit` тем, что попытка не засчитывается: счётчик
    попыток и статус задачи не меняются, достижения не начисляются.
    Песочница запускается столько же раз, поэтому проверка ограничена
    по частоте (429 при превышении).
    """
    if await is_user_limited("task_check", str(current_user.id), CHECK_LIMIT):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много пробных проверок. Попробуйте через минуту.",
            headers={"Retry-After": str(WINDOW_SECONDS)},
        )
    return await service.check_solution(task_id, current_user, payload.code)


@router.get("/{task_id}/attempts", response_model=AttemptList)
async def list_attempts(
    task_id: UUID,
    current_user: CurrentUser,
    service: TaskServiceDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> AttemptList:
    """История попыток ученика по задаче (S42-002), новые сверху.

    В историю попадают только засчитанные отправки: пробная проверка
    (S42-001) попытку не засчитывает и сюда не пишется.
    """
    return await service.list_attempts(
        task_id, current_user, skip=skip, limit=limit
    )


@router.get("/{task_id}/attempts/{attempt_id}", response_model=AttemptDetail)
async def get_attempt(
    task_id: UUID,
    attempt_id: UUID,
    current_user: CurrentUser,
    service: TaskServiceDep,
) -> AttemptDetail:
    """Детальная попытка: код и разбор по тест-кейсам.

    Попытка принадлежит ученику: чужая недоступна (404).
    """
    return await service.get_attempt(task_id, attempt_id, current_user)

@router.patch("/{task_id}/draft", response_model=DraftStatus)
async def save_draft(
    task_id: UUID,
    payload: DraftRequest,
    current_user: CurrentUser,
    service: TaskServiceDep,
) -> DraftStatus:
    """Сохранить черновик решения (S42-003).

    Черновик не является решением: счётчик попыток и статус задачи
    не меняются, в историю попыток запись не попадает. Пустой код
    удаляет черновик.
    """
    return await service.save_draft(task_id, current_user, payload.code)


@router.delete("/{task_id}/draft", response_model=DraftStatus)
async def clear_draft(
    task_id: UUID,
    current_user: CurrentUser,
    service: TaskServiceDep,
) -> DraftStatus:
    """Очистить черновик решения (S42-003)."""
    return await service.clear_draft(task_id, current_user)


# --- Управление задачами (преподаватель/админ) --------------------------


@router.post("", response_model=TaskAdminDetail, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    author: TeacherUser,
    service: TaskServiceDep,
    db: DbSession,
    request: Request,
) -> TaskAdminDetail:
    """Создать задачу (только преподаватель или админ)"""
    task: Task = await service.create_task(payload, author)
    await record_audit(
        db,
        actor=author,
        action="task.created",
        entity_type="task",
        entity_id=task.id,
        payload={"title": task.title, "difficulty": str(task.difficulty)},
        request=request,
    )
    return _admin_detail(task)


@router.patch("/{task_id}", response_model=TaskAdminDetail)
async def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    author: TeacherUser,
    service: TaskServiceDep,
    db: DbSession,
    request: Request,
) -> TaskAdminDetail:
    """Обновить задачу (старое состояние — в историю версий)"""
    task = await service.update_task(task_id, payload, author)
    await record_audit(
        db,
        actor=author,
        action="task.updated",
        entity_type="task",
        entity_id=task_id,
        payload={"fields": sorted(payload.model_dump(exclude_unset=True))},
        request=request,
    )
    return _admin_detail(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    author: TeacherUser,
    service: TaskServiceDep,
    db: DbSession,
    request: Request,
) -> None:
    """Удалить или деактивировать задачу"""
    await service.delete_task(task_id)
    await record_audit(
        db,
        actor=author,
        action="task.deleted",
        entity_type="task",
        entity_id=task_id,
        request=request,
    )


def _admin_detail(task: Task) -> TaskAdminDetail:
    """Собрать ответ для преподавателя"""
    from app.models.task import TaskStatus

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
