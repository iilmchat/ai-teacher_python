"""
Модели данных.

Импорты обязательны: без них `Base.metadata` остаётся пустой и Alembic
не видит таблиц (autogenerate решает, что все таблицы удалены).
"""

from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.code import CodeExecution
from app.models.user import User, UserLevel, UserRole

__all__ = [
    "ChatMessage",
    "ChatSession",
    "CodeExecution",
    "MessageRole",
    "User",
    "UserLevel",
    "UserRole",
]
