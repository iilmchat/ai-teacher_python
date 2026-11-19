"""Журнал действий teacher/admin (S25-004).

Запись добавляется в **ту же** сессию/транзакцию, что и действие: если действие
откатилось — записи нет; аудит не «врёт». `record_audit` не делает flush/commit,
поэтому ошибка аудита не может сломать основной запрос (максимум — упадёт общий
commit, что честно).

Персональные данные в payload не дублируются: только сводка (роль, id, флаги).

S34-003: IP-адрес определяется через `client_ip(request)` с учётом доверенных прокси.
"""

from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import structlog
from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ip_utils import client_ip as resolve_client_ip
from app.models.audit import AuditLog
from app.models.user import User

logger = structlog.get_logger(__name__)

#: Колонки CSV-выгрузки журнала (S47-001, D-006)
AUDIT_CSV_COLUMNS = [
    "created_at",
    "action",
    "actor_username",
    "actor_role",
    "entity_type",
    "entity_id",
    "ip",
]


def client_ip(request: Request | None) -> str | None:
    """IP клиента с учётом `X-Forwarded-For` и `TRUSTED_PROXIES` (S34-003).

    Если request нет — None. Иначе используется общий резолвер `client_ip`,
    который доверяет заголовку только за доверенным прокси.
    """
    if request is None:
        return None
    return resolve_client_ip(request)[:64] or None


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
    search: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[tuple[AuditLog, str | None]], int]:
    """Страница журнала + общее количество по фильтрам.

    Возвращает пары «запись + имя актора»: имя берётся из `users` по
    `actor_id` (у удалённого пользователя FK выставлен в NULL — имя `None`).
    """
    query = select(AuditLog, User.username).outerjoin(
        User, User.id == AuditLog.actor_id
    )
    count_query = select(func.count()).select_from(AuditLog)

    conditions = []
    if action:
        conditions.append(AuditLog.action == action)
    if entity_type:
        conditions.append(AuditLog.entity_type == entity_type)
    if actor_id:
        conditions.append(AuditLog.actor_id == actor_id)
    if search:
        conditions.append(AuditLog.action.ilike(f"%{search.strip()}%"))
    for condition in conditions:
        query = query.where(condition)
        count_query = count_query.where(condition)

    total = int((await db.execute(count_query)).scalar_one())
    rows = (
        await db.execute(
            query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
        )
    ).all()
    return [(row[0], row[1]) for row in rows], total


def _audit_csv_row(log: AuditLog, actor_username: str | None) -> dict[str, str | None]:
    """Одна строка CSV: только действие, актор и сущность (без payload)"""
    return {
        "created_at": log.created_at.isoformat() if log.created_at else None,
        "action": log.action,
        "actor_username": actor_username,
        "actor_role": log.actor_role,
        "entity_type": log.entity_type,
        "entity_id": log.entity_id,
        "ip": log.ip,
    }


async def stream_audit_csv(
    db: AsyncSession,
    *,
    action: str | None = None,
    entity_type: str | None = None,
    actor_id: UUID | None = None,
    search: str | None = None,
    limit: int,
) -> AsyncIterator[bytes]:
    """Потоковый CSV журнала (S47-001, D-006): `utf-8-sig`, серверный курсор.

    Фильтры совпадают с `GET /admin/audit`, поэтому UI и файл дают один и тот
    же набор строк.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=AUDIT_CSV_COLUMNS)
    writer.writeheader()
    # BOM в первом чанке: Excel иначе ломает кириллицу (RULES §11.23).
    yield b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")

    query = select(AuditLog, User.username).outerjoin(
        User, User.id == AuditLog.actor_id
    )
    if action:
        query = query.where(AuditLog.action == action)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if actor_id:
        query = query.where(AuditLog.actor_id == actor_id)
    if search:
        query = query.where(AuditLog.action.ilike(f"%{search.strip()}%"))
    query = query.order_by(AuditLog.created_at.desc())

    result = await db.stream(query)
    count = 0
    async for log, actor_username in result:
        if limit and count >= limit:
            break
        count += 1
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=AUDIT_CSV_COLUMNS)
        writer.writerow(_audit_csv_row(log, actor_username))
        yield buffer.getvalue().encode("utf-8")
