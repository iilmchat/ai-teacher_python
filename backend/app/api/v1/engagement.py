"""
API вовлечения: достижения, статистика, уведомления (S17-001…S17-004).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_active_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.engagement import (
    AchievementItem,
    AchievementsResponse,
    NotificationItem,
    NotificationsReadAllResponse,
    NotificationsResponse,
    StatsResponse,
)
from app.services import engagement_service

router = APIRouter(prefix="/me", tags=["Engagement"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_active_user)]


@router.get("/achievements", response_model=AchievementsResponse)
async def achievements(
    current_user: CurrentUser, db: DbSession
) -> AchievementsResponse:
    """Достижения ученика"""
    rows = await engagement_service.list_achievements(db, current_user.id)
    return AchievementsResponse(
        items=[
            AchievementItem(
                code=achievement.code,
                title=achievement.title,
                description=achievement.description,
                icon=achievement.icon,
                earned_at=earned_at,
            )
            for achievement, earned_at in rows
        ]
    )


@router.get("/stats", response_model=StatsResponse)
async def my_stats(current_user: CurrentUser, db: DbSession) -> StatsResponse:
    """Решено, серия дней, попытки, активность в чате"""
    data = await engagement_service.stats(db, current_user.id)
    return StatsResponse(**data)  # type: ignore[arg-type]


@router.get("/notifications", response_model=NotificationsResponse)
async def notifications(
    current_user: CurrentUser,
    db: DbSession,
    unread_only: bool = False,
    type: str | None = Query(default=None, max_length=30),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> NotificationsResponse:
    """Уведомления; перед выдачей добавляет напоминания о дедлайнах.

    Пагинация — additive (S19-004); фильтр `type` — additive (S47-005).
    `unread` всегда считается по всем уведомлениям, а не по фильтру: это
    счётчик для бейджа.
    """
    await engagement_service.sync_deadline_notifications(db, current_user.id)
    items, unread = await engagement_service.list_notifications(
        db,
        current_user.id,
        unread_only=unread_only,
        notification_type=type,
        skip=skip,
        limit=limit,
    )
    return NotificationsResponse(
        items=[NotificationItem.model_validate(item) for item in items],
        unread=unread,
    )


@router.post(
    "/notifications/read-all", response_model=NotificationsReadAllResponse
)
async def read_all_notifications(
    current_user: CurrentUser, db: DbSession
) -> NotificationsReadAllResponse:
    """Отметить все уведомления прочитанными (S47-005)."""
    updated = await engagement_service.mark_all_read(db, current_user.id)
    return NotificationsReadAllResponse(updated=updated)


@router.post(
    "/notifications/{notification_id}/read", response_model=NotificationItem
)
async def read_notification(
    notification_id: UUID, current_user: CurrentUser, db: DbSession
) -> NotificationItem:
    """Отметить уведомление прочитанным"""
    notification = await engagement_service.mark_read(
        db, current_user.id, notification_id
    )
    return NotificationItem.model_validate(notification)
