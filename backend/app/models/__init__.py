"""
Модели данных.

Импорты обязательны: без них `Base.metadata` остаётся пустой и Alembic
не видит таблиц (autogenerate решает, что все таблицы удалены).
"""

from app.models.audit import AuditLog
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.classroom import (
    Assignment,
    AssignmentTemplate,
    Classroom,
    ClassroomMember,
    ClassroomRole,
)
from app.models.code import CodeExecution
from app.models.engagement import Achievement, Notification, UserAchievement
from app.models.task import (
    AttemptFeedback,
    Task,
    TaskAttempt,
    TaskDifficulty,
    TaskStatus,
    TaskVersion,
    UserTaskProgress,
)
from app.models.user import User, UserLevel, UserRole, UserSession

__all__ = [
    "AuditLog",
    "Achievement",
    "Assignment",
    "AssignmentTemplate",
    "AttemptFeedback",
    "ChatMessage",
    "ChatSession",
    "Classroom",
    "ClassroomMember",
    "ClassroomRole",
    "CodeExecution",
    "MessageRole",
    "Notification",
    "Task",
    "TaskAttempt",
    "TaskDifficulty",
    "TaskStatus",
    "TaskVersion",
    "User",
    "UserAchievement",
    "UserLevel",
    "UserRole",
    "UserSession",
    "UserTaskProgress",
]
