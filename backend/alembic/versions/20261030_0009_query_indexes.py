"""query optimization indexes

Revision ID: 009
Revises: 008
Create Date: 2026-10-30

Индексы под фильтры и сортировки, которые появились в S19-004:
- каталог задач (is_active + created_at);
- список учеников в кабинете учителя (role + last_active);
- постраничные уведомления (user_id + created_at);
- «мои задания» по дедлайну (assignments.due_at);
- история сессии чата (session_id + created_at).

Индексы `classrooms.owner_id`, `classrooms.join_code` (UNIQUE),
`classroom_members.user_id`, `notifications(user_id, read_at)` и
`task_versions.task_id` уже созданы миграциями 001, 006, 007 и 008 —
повторно их не создаём, чтобы `alembic check` не видел дублей.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("idx_tasks_active_created", "tasks", ["is_active", "created_at"])
    op.create_index(
        "idx_users_role_last_active", "users", ["role", "last_active"]
    )
    op.create_index(
        "idx_notifications_user_created",
        "notifications",
        ["user_id", "created_at"],
    )
    op.create_index("idx_assignments_due_at", "assignments", ["due_at"])
    op.create_index(
        "idx_chat_messages_session_created",
        "chat_messages",
        ["session_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_chat_messages_session_created", table_name="chat_messages")
    op.drop_index("idx_assignments_due_at", table_name="assignments")
    op.drop_index("idx_notifications_user_created", table_name="notifications")
    op.drop_index("idx_users_role_last_active", table_name="users")
    op.drop_index("idx_tasks_active_created", table_name="tasks")
