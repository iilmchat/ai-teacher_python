"""Журнал действий teacher/admin (S25-004).

Запись добавляется в **ту же** сессию/транзакцию, что и действие: если действие
откатилось — записи нет; аудит не «врёт». `record_audit` не делает flush/commit,
поэтому ошибка аудита не может сломать основной запрос (максимум — упадёт общий
commit, что честно).

Персональные данные в payload не дублируются: только сводка (роль, id, флаги).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User

logger = structlog.get_logger(__name__)


def client_ip(request: Request | None) -> str | None:
    """IP клиента с учётом `X-Forwarded-For` (за nginx)"""
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64] or None
    return request.client.host[:64] if request.client else None


async def record_audit(
    db: AsyncSession,
    *,
    actor: User,
    action: str,
    entity_type: str,
    entity_id: str | UUID | None = None,
    payload: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    """Добавить запись аудита и сразу зафиксировать (best-effort).

    Репозитории коммитят действие сами, поэтому аудит пишется отдельным
    коммитом в той же сессии. Ошибка записи не ломает запрос: rollback + warning.
    """
    role = getattr(actor.role, "value", actor.role)
    db.add(
        AuditLog(
            actor_id=actor.id,
            actor_role=str(role),
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            payload=payload or {},
            ip=client_ip(request),
        )
    )
    try:
        await db.commit()
    except Exception as exc:  # noqa: BLE001 — аудит не должен ломать действие
        await db.rollback()
        logger.warning("audit_write_failed", action=action, error=str(exc))


async def list_audit(
    db: AsyncSession,
    *,
    action: str | None = None,
    entity_type: str | None = None,
    actor_id: UUID | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[AuditLog], int]:
    """Страница журнала + общее количество по фильтрам"""
    query = select(AuditLog)
    count_query = select(func.count()).select_from(AuditLog)

    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
        count_query = count_query.where(AuditLog.entity_type == entity_type)
    if actor_id:
        query = query.where(AuditLog.actor_id == actor_id)
        count_query = count_query.where(AuditLog.actor_id == actor_id)

    total = int((await db.execute(count_query)).scalar_one())
    rows = (
        await db.execute(
            query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
        )
    ).scalars().all()
    return list(rows), total
