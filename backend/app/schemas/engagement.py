"""Схемы вовлечения (S17)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AchievementItem(BaseModel):
    """Полученное достижение"""

    code: str
    title: str
    description: str
    icon: str
    earned_at: datetime


class AchievementsResponse(BaseModel):
    items: list[AchievementItem] = Field(default_factory=list)


class StatsResponse(BaseModel):
    """Личная статистика ученика"""

    solved: int
    attempts: int
    avg_attempts: float
    streak_days: int
    achievements_count: int
    chat_sessions: int
    chat_messages: int


class NotificationItem(BaseModel):
    """Уведомление"""

    id: UUID
    type: str
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationsResponse(BaseModel):
    items: list[NotificationItem] = Field(default_factory=list)
    unread: int = 0
