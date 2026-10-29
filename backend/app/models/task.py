"""
Модели задач и прогресса обучения (S7-001).
"""

import enum
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class TaskDifficulty(str, enum.Enum):
    """Сложность задачи"""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class TaskStatus(str, enum.Enum):
    """Статус прохождения задачи учеником"""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


def _enum_values(enum_cls: Any) -> list[str]:
    """Хранить в БД значения, а не имена членов enum (KI-004)"""
    return [member.value for member in enum_cls]


class Task(Base):
    """Учебная задача"""

    __tablename__ = "tasks"
    __table_args__ = (
        Index("idx_tasks_difficulty", "difficulty"),
        Index("idx_tasks_category", "category"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[TaskDifficulty] = mapped_column(
        Enum(TaskDifficulty, values_callable=_enum_values),
        nullable=False,
        default=TaskDifficulty.EASY,
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    # [{"input": "...", "expected_output": "...", "description": "..."}]
    test_cases: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    hints: Mapped[list[str]] = mapped_column(JSONB, default=list)
    solution_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    progress: Mapped[list["UserTaskProgress"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Task {self.title} ({self.difficulty.value})>"


class UserTaskProgress(Base):
    """Прогресс ученика по конкретной задаче"""

    __tablename__ = "user_task_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "task_id", name="uq_progress_user_task"),
        Index("idx_progress_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, values_callable=_enum_values),
        nullable=False,
        default=TaskStatus.NOT_STARTED,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    best_solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    task: Mapped["Task"] = relationship(back_populates="progress")

    def __repr__(self) -> str:
        return f"<UserTaskProgress user={self.user_id} status={self.status.value}>"
