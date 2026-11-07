"""Активные сессии пользователя — user_sessions (S45-005).

Revision ID: 019
Revises: 018
Create Date: 2026-11-07

Аддитивная миграция: одна строка на вход (устройство). `jti` — идентификатор
refresh-токена (ротируется при обновлении), `user_agent` и `ip` — для списка
сессий (PRIVACY.md), `revoked_at` — отзыв. Смена пароля и «выйти везде»
отзывают строки и увеличивают `users.token_version`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("jti", sa.String(length=36), nullable=False),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="user_sessions_user_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="user_sessions_pkey"),
        sa.UniqueConstraint("jti", name="user_sessions_jti_key"),
    )
    op.create_index(
        "idx_user_sessions_user", "user_sessions", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("idx_user_sessions_user", table_name="user_sessions")
    op.drop_table("user_sessions")
