"""
Модели классов и назначений (S16-001).
"""

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ClassroomRole(str, enum.Enum):
    """Роль участника класса"""

    OWNER = "owner"
    STUDENT = "student"


class Classroom(Base):
    """Класс (группа учеников)"""

    __tablename__ = "classrooms"
    __table_args__ = (Index("idx_classrooms_owner", "owner_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    join_code: Mapped[str] = mapped_column(
        String(12), nullable=False, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    members: Mapped[list["ClassroomMember"]] = relationship(
        back_populates="classroom", cascade="all, delete-orphan"
    )
    assignments: Mapped[list["Assignment"]] = relationship(
        back_populates="classroom", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Classroom {self.name} ({self.join_code})>"


class ClassroomMember(Base):
    """Участник класса"""

    __tablename__ = "classroom_members"
    __table_args__ = (
        UniqueConstraint("classroom_id", "user_id", name="uq_classroom_member"),
        Index("idx_classroom_members_user", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    classroom_id: Mapped[UUID] = mapped_column(
        ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ClassroomRole.STUDENT.value
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    classroom: Mapped["Classroom"] = relationship(back_populates="members")

    def __repr__(self) -> str:
        return f"<ClassroomMember classroom={self.classroom_id} user={self.user_id}>"


class Assignment(Base):
    """Назначение задачи классу"""

    __tablename__ = "assignments"
    __table_args__ = (
        UniqueConstraint("classroom_id", "task_id", name="uq_assignment_task"),
        Index("idx_assignments_classroom", "classroom_id"),
        # S19-004: фильтр/сортировка «моих заданий» по дедлайну
        Index("idx_assignments_due_at", "due_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    classroom_id: Mapped[UUID] = mapped_column(
        ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    classroom: Mapped["Classroom"] = relationship(back_populates="assignments")

    def __repr__(self) -> str:
        return f"<Assignment classroom={self.classroom_id} task={self.task_id}>"

class AssignmentTemplate(Base):
    """Шаблон назначений учителя (S28-002).

    Набор задач, который можно применить к классу одним действием. Принадлежит
    учителю; `task_ids` хранится как JSONB-массив UUID-строк, чтобы шаблон не
    ломался при удалении задачи (при применении несуществующие id пропускаются).
    """

    __tablename__ = "assignment_templates"
    __table_args__ = (
        Index("idx_assignment_templates_owner", "owner_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    task_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<AssignmentTemplate {self.name} owner={self.owner_id}>"


class ClassroomAnnouncement(Base):
    """Объявление класса (S46-006).

    Публикуется учителем; ученики класса видят его на странице класса и в
    «Моих заданиях». Удалить может автор или владелец класса.
    """

    __tablename__ = "classroom_announcements"
    __table_args__ = (
        Index("idx_classroom_announcements_classroom", "classroom_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    classroom_id: Mapped[UUID] = mapped_column(
        ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<ClassroomAnnouncement {self.title} "
            f"classroom={self.classroom_id}>"
        )
