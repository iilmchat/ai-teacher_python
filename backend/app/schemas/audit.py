"""Схемы журнала действий (S25-004)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditLogItem(BaseModel):
    """Запись журнала действий"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_id: UUID | None = None
    actor_role: str
    action: str
    entity_type: str
    entity_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    ip: str | None = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    """Страница журнала"""

    items: list[AuditLogItem]
    total: int
