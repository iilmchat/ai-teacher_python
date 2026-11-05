"""Аудит действий teacher/admin (S25-004).

Таблица `audit_log` — кто, что, над чем и когда сделал. Пишется в тех же
транзакциях, что и само действие (best-effort: ошибка аудита не ломает запрос,
только warning в лог). Персональные данные не дублируются: payload — сводка
(например, `{"role": "teacher"}`), без паролей и токенов.
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class AuditLog(Base):
    """Запись журнала действий"""

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("idx_audit_log_created", "created_at"),
        Index("idx_audit_log_action_created", "action", "created_at"),
        Index("idx_audit_log_actor_created", "actor_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    #: Актор (NULL — если пользователь удалён; actor_role сохраняется)
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_role: Mapped[str] = mapped_column(String(30), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Сводка изменения (без секретов/PII)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} {self.entity_type}={self.entity_id}>"
