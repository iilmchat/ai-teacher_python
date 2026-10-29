"""
Модели данных.

Импорты обязательны: без них `Base.metadata` остаётся пустой и Alembic
не видит таблиц (autogenerate решает, что все таблицы удалены).
"""

from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.classroom import Assignment, Classroom, ClassroomMember, ClassroomRole
from app.models.code import CodeExecution
from app.models.task import (
    Task,
    TaskDifficulty,
    TaskStatus,
    TaskVersion,
    UserTaskProgress,
)
from app.models.user import User, UserLevel, UserRole

__all__ = [
    "Assignment",
    "ChatMessage",
    "ChatSession",
    "Classroom",
    "ClassroomMember",
    "ClassroomRole",
    "CodeExecution",
    "MessageRole",
    "Task",
    "TaskDifficulty",
    "TaskStatus",
    "TaskVersion",
    "User",
    "UserLevel",
    "UserRole",
    "UserTaskProgress",
]
