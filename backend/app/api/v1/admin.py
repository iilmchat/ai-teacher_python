"""
Admin API (S10-004): пользователи, задачи, аналитика.

Все маршруты требуют роль администратора (`require_role(UserRole.ADMIN)`).
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import require_role
from app.db.database import get_db
from app.db.repositories.user import UserRepository
from app.models.task import Task
from app.models.user import User, UserRole
from app.schemas.admin import (
    AdminQualityResponse,
    AdminTaskItem,
    AdminTaskListResponse,
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
)
from app.schemas.audit import AuditLogItem, AuditLogListResponse
from app.services.analytics_service import AnalyticsService
from app.services.audit_service import (
    list_audit,
    record_audit,
    stream_audit_csv,
)
from app.services.cache import cache_metrics
from app.services.export_service import stream_csv, stream_json
from app.services.feedback_service import FeedbackService
from app.services.llm.metrics import llm_metrics

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
    search: str | None = Query(default=None, max_length=64),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> AuditLogListResponse:
    """Журнал действий teacher/admin (S25-004), новые сверху.

    S47-001: поиск по `action` (ILIKE) и имя актора из `users`.
    """
    rows, total = await list_audit(
        db,
        action=action,
        entity_type=entity_type,
        actor_id=actor_id,
        search=search,
        skip=skip,
        limit=limit,
    )
    return AuditLogListResponse(
        items=[_audit_item(log, username) for log, username in rows],
        total=total,
    )


def _audit_item(log: Any, actor_username: str | None) -> AuditLogItem:
    """Запись журнала с именем актора (join `users`)"""
    return AuditLogItem(
        id=log.id,
        actor_id=log.actor_id,
        actor_username=actor_username,
        actor_role=log.actor_role,
        action=log.action,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        payload=log.payload or {},
        ip=log.ip,
        created_at=log.created_at,
    )


@router.get("/audit/export")
async def export_audit(
    admin: AdminUser,
    db: DbSession,
    request: Request,
    action: str | None = Query(default=None, max_length=64),
    entity_type: str | None = Query(default=None, max_length=64),
    actor_id: UUID | None = None,
    search: str | None = Query(default=None, max_length=64),
) -> StreamingResponse:
    """CSV журнала аудита с теми же фильтрами, что и список (S47-001, D-006).

    Отдельный потоковый эндпоинт: набор колонок журнала не совпадает с
    аналитическими наборами `export_service`.
    """
    limit = max(0, settings.export_max_rows)
    await record_audit(
        db,
        actor=admin,
        action="audit.exported",
        entity_type="audit",
        payload={
            "action": action,
            "entity_type": entity_type,
            "actor_id": str(actor_id) if actor_id else None,
            "has_search": bool(search),
            "limit": limit,
        },
        request=request,
    )

    async def body() -> AsyncIterator[bytes]:
        async for chunk in stream_audit_csv(
            db,
            action=action,
            entity_type=entity_type,
            actor_id=actor_id,
            search=search,
            limit=limit,
        ):
            yield chunk

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return StreamingResponse(
        body(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="audit-{stamp}.csv"',
            "X-Export-Limit": str(limit),
        },
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


@router.get("/quality", response_model=AdminQualityResponse)
async def get_quality(_: AdminUser, db: DbSession) -> AdminQualityResponse:
    """Сводка качества ответов ассистента по оценкам учеников (S43-003).

    Негативные оценки с текстом ответа — вход для LLM-as-judge
    (см. `docs/LLM_EVAL.md`).
    """
    summary = await FeedbackService(db).quality_summary()
    return AdminQualityResponse.model_validate(summary)


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
