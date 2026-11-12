"""
Admin API (S10-004): пользователи, задачи, аналитика.

Все маршруты требуют роль администратора (`require_role(UserRole.ADMIN)`).
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import require_role
from app.db.database import get_db
from app.db.repositories.user import UserRepository
from app.models.task import Task, TaskDifficulty
from app.models.user import User, UserRole
from app.schemas.admin import (
    AdminQualityResponse,
    AdminTaskItem,
    AdminTaskListResponse,
    AdminTaskReviewResponse,
    AdminUserItem,
    AdminUserListResponse,
    AdminUserUpdate,
    AnalyticsActivity,
    AnalyticsCache,
    AnalyticsLearning,
    AnalyticsLLM,
    AnalyticsResponse,
    AnalyticsTasks,
    AnalyticsUsers,
    DeleteResponse,
    ModerationSource,
    TaskModerateRequest,
    TaskModerateResponse,
)
from app.schemas.audit import AuditLogItem, AuditLogListResponse
from app.services.analytics_service import AnalyticsService
from app.services.audit_service import list_audit, record_audit
from app.services.cache import (
    cache_get_json,
    cache_metrics,
    cache_set_json,
    quality_cache_key,
)
from app.services.export_service import stream_csv, stream_json
from app.services.feedback_service import FeedbackService
from app.services.llm.metrics import llm_metrics
from app.services.moderation_service import ModerationService

router = APIRouter(prefix="/admin", tags=["Admin"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]


@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    _: AdminUser,
    db: DbSession,
    role: UserRole | None = None,
    search: str | None = Query(default=None, max_length=100),
    skip: int = 0,
    limit: int = 50,
) -> AdminUserListResponse:
    """Список пользователей с фильтрами"""
    query = select(User)
    count_query = select(func.count()).select_from(User)

    if role is not None:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    if search:
        pattern = f"%{search.lower()}%"
        condition = func.lower(User.username).like(pattern) | func.lower(User.email).like(
            pattern
        )
        query = query.where(condition)
        count_query = count_query.where(condition)

    total = int((await db.execute(count_query)).scalar_one())
    result = await db.execute(
        query.order_by(User.created_at.desc()).offset(skip).limit(limit)
    )
    items = [AdminUserItem.model_validate(user) for user in result.scalars().all()]
    return AdminUserListResponse(total=total, items=items)


@router.patch("/users/{user_id}", response_model=AdminUserItem)
async def update_user(
    user_id: UUID,
    payload: AdminUserUpdate,
    admin: AdminUser,
    db: DbSession,
    request: Request,
) -> AdminUserItem:
    """Изменить роль или уровень пользователя"""
    repo = UserRepository(db)
    user = await repo.get(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return AdminUserItem.model_validate(user)

    # Нельзя снять с себя роль администратора — иначе можно потерять доступ
    if user.id == admin.id and data.get("role") not in (None, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя понизить собственную роль администратора",
        )

    updated = await repo.update(user_id, **data)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    await record_audit(
        db,
        actor=admin,
        action="user.updated",
        entity_type="user",
        entity_id=user_id,
        payload={key: str(value) for key, value in data.items()},
        request=request,
    )
    return AdminUserItem.model_validate(updated)


@router.delete("/users/{user_id}", response_model=DeleteResponse)
async def delete_user(
    user_id: UUID,
    admin: AdminUser,
    db: DbSession,
    request: Request,
) -> DeleteResponse:
    """Удалить пользователя со всеми его данными"""
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя удалить собственную учётную запись",
        )

    repo = UserRepository(db)
    deleted = await repo.delete(user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    await record_audit(
        db,
        actor=admin,
        action="user.deleted",
        entity_type="user",
        entity_id=user_id,
        request=request,
    )
    return DeleteResponse(deleted=True)


@router.get("/audit", response_model=AuditLogListResponse)
async def list_audit_log(
    _: AdminUser,
    db: DbSession,
    action: str | None = Query(default=None, max_length=64),
    entity_type: str | None = Query(default=None, max_length=64),
    actor_id: UUID | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> AuditLogListResponse:
    """Журнал действий teacher/admin (S25-004), новые сверху"""
    items, total = await list_audit(
        db,
        action=action,
        entity_type=entity_type,
        actor_id=actor_id,
        skip=skip,
        limit=limit,
    )
    return AuditLogListResponse(
        items=[AuditLogItem.model_validate(item) for item in items],
        total=total,
    )


@router.get("/tasks", response_model=AdminTaskListResponse)
async def list_tasks(
    _: AdminUser, db: DbSession, skip: int = 0, limit: int = 100
) -> AdminTaskListResponse:
    """Все задачи, включая деактивированные"""
    total = int(
        (await db.execute(select(func.count()).select_from(Task))).scalar_one()
    )
    result = await db.execute(
        select(Task).order_by(Task.created_at.desc()).offset(skip).limit(limit)
    )
    items = [
        AdminTaskItem(
            id=task.id,
            title=task.title,
            difficulty=task.difficulty,
            category=task.category,
            is_active=task.is_active,
            test_cases_count=len(task.test_cases or []),
            hints_count=len(task.hints or []),
            created_at=task.created_at,
            created_by=task.created_by,
        )
        for task in result.scalars().all()
    ]
    return AdminTaskListResponse(total=total, items=items)


@router.get("/tasks/review", response_model=AdminTaskReviewResponse)
async def review_tasks(
    _: AdminUser,
    db: DbSession,
    source: ModerationSource | None = None,
    difficulty: TaskDifficulty | None = None,
    threshold: int = Query(default=3, ge=1, le=20),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> AdminTaskReviewResponse:
    """Очередь модерации: только LLM-генерация и импорт (S47-003).

    Метрики «застревания»: попытки, доля успешных, среднее число попыток,
    число учеников и число застрявших (attempts > threshold без завершения).
    Сортировка — сначала самые проблемные.
    """
    return await ModerationService(db).list_review_queue(
        source=source,
        difficulty=difficulty,
        threshold=threshold,
        skip=skip,
        limit=limit,
    )


@router.post("/tasks/{task_id}/moderate", response_model=TaskModerateResponse)
async def moderate_task(
    task_id: UUID,
    payload: TaskModerateRequest,
    admin: AdminUser,
    db: DbSession,
    request: Request,
) -> TaskModerateResponse:
    """Действие модератора: publish / unpublish / return_to_revision (S47-003).

    Ручные задачи в очередь не попадают, но снять с публикации можно любую.
    Аудит `task.moderated` не содержит текст комментария — только длину.
    """
    task = await ModerationService(db).moderate(
        task_id, action=payload.action, comment=payload.comment
    )
    audit_payload: dict[str, object] = {"action": payload.action}
    if payload.action == "return_to_revision" and payload.comment:
        audit_payload["comment_length"] = len(payload.comment)
    await record_audit(
        db,
        actor=admin,
        action="task.moderated",
        entity_type="task",
        entity_id=task.id,
        payload=audit_payload,
        request=request,
    )
    return TaskModerateResponse(
        id=task.id,
        title=task.title,
        action=payload.action,
        source=task.source,
        is_active=task.is_active,
        moderation_comment=task.moderation_comment,
    )


@router.get("/quality", response_model=AdminQualityResponse)
async def get_quality(_: AdminUser, db: DbSession) -> AdminQualityResponse:
    """Сводка качества ответов ассистента по оценкам учеников (S43-003).

    Тяжёлые агрегаты кэшируются на 60 с (S39-003); инвалидация — при
    изменении/удалении оценки (`FeedbackService`). Для админского экрана
    задержка в минуту допустима; свежесть гарантируется инвалидацией.
    """
    key = quality_cache_key()
    cached = await cache_get_json(key)
    if isinstance(cached, dict):
        return AdminQualityResponse.model_validate(cached)

    summary = await FeedbackService(db).quality_summary()
    response = AdminQualityResponse.model_validate(summary)
    await cache_set_json(key, response.model_dump(mode="json"), ttl=60)
    return response


@router.get("/quality/export")
async def export_quality(
    admin: AdminUser,
    db: DbSession,
    request: Request,
    format_: Literal["csv", "json"] = Query(default="csv", alias="format"),
) -> StreamingResponse:
    """Выгрузка негативных оценок ассистента (S47-004/D-008).

    Потоково, через серверный курсор; лимит — `EXPORT_MAX_ROWS`. Выгружаются
    только оценки `value < 0`, с уровнем помощи из сессии и задачей из
    `message_metadata.task_context` (или «без задачи»).
    """
    limit = max(0, settings.export_max_rows)
    await record_audit(
        db,
        actor=admin,
        action="quality.exported",
        entity_type="quality",
        payload={"format": format_, "limit": limit},
        request=request,
    )

    async def body() -> AsyncIterator[bytes]:
        stream = (
            stream_csv(db, "negative_feedback", limit=limit)
            if format_ == "csv"
            else stream_json(db, "negative_feedback", limit=limit)
        )
        async for chunk in stream:
            yield chunk

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    media_type = "text/csv; charset=utf-8" if format_ == "csv" else "application/json"
    headers = {
        "Content-Disposition": (
            f'attachment; filename="quality-negative-{stamp}.{format_}"'
        ),
        "X-Export-Limit": str(limit),
    }
    return StreamingResponse(body(), media_type=media_type, headers=headers)


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(_: AdminUser, db: DbSession) -> AnalyticsResponse:
    """Сводная аналитика для дашборда (БД + метрики LLM и кэша из памяти)"""
    raw = await AnalyticsService(db).summary()
    return AnalyticsResponse(
        users=AnalyticsUsers(**raw["users"]),  # type: ignore[arg-type]
        tasks=AnalyticsTasks(**raw["tasks"]),  # type: ignore[arg-type]
        learning=AnalyticsLearning(**raw["learning"]),  # type: ignore[arg-type]
        activity=AnalyticsActivity(**raw["activity"]),  # type: ignore[arg-type]
        llm=AnalyticsLLM.model_validate(llm_metrics.snapshot()),
        cache=AnalyticsCache(**cache_metrics.snapshot()),
        generated_at=str(raw["generated_at"]),
    )


@router.get("/analytics/export")
async def export_analytics(
    admin: AdminUser,
    db: DbSession,
    request: Request,
    dataset: Literal["users", "tasks", "attempts", "activity"] = "users",
    format_: Literal["csv", "json"] = Query(default="csv", alias="format"),
) -> StreamingResponse:
    """Экспорт аналитики CSV/JSON (S26-001), потоково, с лимитом строк.

    Стрим открывает **свою** сессию: сессия запроса закрывается вместе с
    ответом, а генератор живёт дольше — общая сессия ломала бы выгрузку.
    """
    limit = max(0, settings.export_max_rows)
    await record_audit(
        db,
        actor=admin,
        action="analytics.exported",
        entity_type="analytics",
        payload={"dataset": dataset, "format": format_, "limit": limit},
        request=request,
    )

    async def body() -> AsyncIterator[bytes]:
        stream = (
            stream_csv(db, dataset, limit=limit)
            if format_ == "csv"
            else stream_json(db, dataset, limit=limit)
        )
        async for chunk in stream:
            yield chunk

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    media_type = "text/csv; charset=utf-8" if format_ == "csv" else "application/json"
    headers = {
        "Content-Disposition": (
            f'attachment; filename="export-{dataset}-{stamp}.{format_}"'
        ),
        "X-Export-Limit": str(limit),
    }
    return StreamingResponse(body(), media_type=media_type, headers=headers)
