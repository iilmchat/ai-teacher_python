"""Оценки ответов ассистента — message_feedback (S43-003)

Revision ID: 017
Revises: 016
Create Date: 2026-11-06

Аддитивная миграция: таблица оценок ответа ассистента. Одна оценка на
пару «сообщение × ученик» (уникальное ограничение), значение +1 или −1 и
необязательный комментарий до 500 символов.

Оценки — источник данных для сводки качества у администратора и вход для
LLM-as-judge (см. `docs/LLM_EVAL.md`).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "message_feedback",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("value", sa.SmallInteger(), nullable=False),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "value IN (-1, 1)", name="ck_message_feedback_value"
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["chat_messages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id", "user_id", name="uq_message_feedback_message_user"
        ),
    )
    op.create_index(
        "idx_message_feedback_message", "message_feedback", ["message_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_message_feedback_message", table_name="message_feedback")
    op.drop_table("message_feedback")
