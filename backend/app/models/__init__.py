"""
Модели данных.

Импорты обязательны: без них `Base.metadata` остаётся пустой и Alembic
не видит таблиц (autogenerate решает, что все таблицы удалены).
"""

from app.models.audit import AuditLog
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.classroom import Assignment, Classroom, ClassroomMember, ClassroomRole
from app.models.code import CodeExecution
from app.models.engagement import Achievement, Notification, UserAchievement
from app.models.task import (
    Task,
    TaskDifficulty,
    TaskStatus,
    TaskVersion,
    UserTaskProgress,
)
from app.models.user import User, UserLevel, UserRole

__all__ = [
    "AuditLog",
    "Achievement",
    "Assignment",
    "ChatMessage",
    "ChatSession",
    "Classroom",
    "ClassroomMember",
    "ClassroomRole",
    "CodeExecution",
    "MessageRole",
    "Notification",
    "Task",
    "TaskDifficulty",
    "TaskStatus",
    "TaskVersion",
    "User",
    "UserAchievement",
    "UserLevel",
    "UserRole",
    "UserTaskProgress",
]
