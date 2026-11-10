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


class TaskSource(str, enum.Enum):
    """Происхождение задачи (S47-003).

    Модерация касается только LLM-генерации и импорта (решения D-002/D-003):
    задачи, созданные учителем вручную, публикуются сразу и в очередь не
    попадают.
    """

    MANUAL = "manual"
    GENERATED = "generated"
    IMPORTED = "imported"


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
        Index("idx_tasks_tags", "tags", postgresql_using="gin"),
        # S19-004: каталог фильтрует по is_active и сортирует по created_at
        Index("idx_tasks_active_created", "is_active", "created_at"),
        # S47-003: очередь модерации фильтрует по source и сортирует по дате
        Index("idx_tasks_source_created", "source", "created_at"),
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
    #: Происхождение задачи: manual | generated | imported (S47-003)
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TaskSource.MANUAL.value,
        server_default=TaskSource.MANUAL.value,
    )
    #: Комментарий модератора при возврате в доработку (S47-003)
    moderation_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Теги для поиска и группировки (S14-004)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
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
    versions: Mapped[list["TaskVersion"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Task {self.title} ({self.difficulty.value})>"


class TaskVersion(Base):
    """Снимок задачи перед правкой (S14-005).

    Правка тест-кейсов «ломает» уже сданные решения, поэтому история версий
    позволяет посмотреть, что было, и откатиться.
    """

    __tablename__ = "task_versions"
    __table_args__ = (
        UniqueConstraint("task_id", "version", name="uq_task_version"),
        Index("idx_task_versions_task", "task_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Полный снимок полей задачи на момент версии
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    task: Mapped["Task"] = relationship(back_populates="versions")

    def __repr__(self) -> str:
        return f"<TaskVersion task={self.task_id} v{self.version}>"


class TaskAttempt(Base):
    """Попытка ученика по задаче (S42-002)

    `UserTaskProgress` хранит сводку (статус, счётчик попыток), а эта таблица —
    историю: код, который ученик отправил, результат по каждому тест-кейсу и
    время. Создаётся только при засчитанной отправке (`POST /tasks/{id}/submit`);
    пробная проверка (S42-001) попытку не засчитывает и в историю не пишется.
    """

    __tablename__ = "task_attempts"
    __table_args__ = (
        Index("idx_task_attempts_user_task", "user_id", "task_id", "created_at"),
        Index("idx_task_attempts_task", "task_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    #: Код, который ученик отправил
    code: Mapped[str] = mapped_column(Text, nullable=False)
    #: Пройдены ли все тест-кейсы
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    passed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    #: Разбор по кейсам: список словарей с input/expected/actual/error
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<TaskAttempt user={self.user_id} task={self.task_id} "
            f"passed={self.passed}>"
        )


class AttemptFeedback(Base):
    """Комментарий учителя к попытке ученика (S46-002)

    Один учитель оставляет один комментарий на попытку: повторная отправка
    обновляет текст, а не создаёт дубль. Ученик видит комментарий в истории
    попыток и получает in-app уведомление.
    """

    __tablename__ = "attempt_feedback"
    __table_args__ = (
        UniqueConstraint(
            "attempt_id", "teacher_id", name="uq_attempt_feedback_teacher"
        ),
        Index("idx_attempt_feedback_attempt", "attempt_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    attempt_id: Mapped[UUID] = mapped_column(
        ForeignKey("task_attempts.id", ondelete="CASCADE"), nullable=False
    )
    teacher_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<AttemptFeedback attempt={self.attempt_id} teacher={self.teacher_id}>"


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
    #: Незавершённый код ученика (S42-003). Хранится между сессиями,
    #: чтобы работа не терялась при перезагрузке страницы. Не является
    #: решением: в попытки не попадает и в `best_solution` не пишется.
    draft_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Когда черновик сохранён в последний раз
    draft_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    task: Mapped["Task"] = relationship(back_populates="progress")

    def __repr__(self) -> str:
        return f"<UserTaskProgress user={self.user_id} status={self.status.value}>"
