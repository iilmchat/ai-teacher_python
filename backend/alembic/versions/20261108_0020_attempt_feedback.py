"""Комментарии учителя к попыткам — attempt_feedback (S46-002).

Revision ID: 020
Revises: 019
Create Date: 2026-11-08

Аддитивная миграция: один комментарий учителя на попытку (уникальная пара
`attempt_id` + `teacher_id`). Повторная отправка обновляет текст, поэтому
отдельного `updated_at` нет. Удаляется вместе с попыткой.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attempt_feedback",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "attempt_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "teacher_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["task_attempts.id"],
            name="attempt_feedback_attempt_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["teacher_id"],
            ["users.id"],
            name="attempt_feedback_teacher_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="attempt_feedback_pkey"),
        sa.UniqueConstraint(
            "attempt_id",
            "teacher_id",
            name="uq_attempt_feedback_teacher",
        ),
    )
    op.create_index(
        "idx_attempt_feedback_attempt",
        "attempt_feedback",
        ["attempt_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_attempt_feedback_attempt", table_name="attempt_feedback"
    )
    op.drop_table("attempt_feedback")
