"""
Модель истории выполнений кода (S6-004).
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class CodeExecution(Base):
    """Запись о запуске кода ученика в песочнице"""

    __tablename__ = "code_executions"
    __table_args__ = (Index("idx_code_executions_user", "user_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    output: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    execution_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        status = "ok" if self.success else "error"
        return f"<CodeExecution {self.id} ({status})>"
