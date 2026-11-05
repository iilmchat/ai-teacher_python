"""title и pinned у сессий чата — управление сессиями (S43-001)

Revision ID: 016
Revises: 015
Create Date: 2026-11-05

Аддитивная миграция: `title` (nullable) хранит авто-заголовок из первого
вопроса или переименование пользователя, `pinned` поднимает закреплённые
сессии в начало списка. Индекс `(user_id, pinned, updated_at)` обслуживает
сортировку «закреплённые сверху, затем свежие».

Существующие сессии получают `title = NULL` (заголовок появится после
первого нового сообщения или переименования) и `pinned = false`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_sessions", sa.Column("title", sa.String(length=120), nullable=True)
    )
    op.add_column(
        "chat_sessions",
        sa.Column(
            "pinned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "idx_chat_sessions_user_pinned_updated",
        "chat_sessions",
        ["user_id", "pinned", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_chat_sessions_user_pinned_updated", table_name="chat_sessions")
    op.drop_column("chat_sessions", "pinned")
    op.drop_column("chat_sessions", "title")
