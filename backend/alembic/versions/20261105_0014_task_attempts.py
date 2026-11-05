"""task_attempts — история попыток ученика (S42-002)

Revision ID: 014
Revises: 013
Create Date: 2026-11-05

Аддитивная миграция: таблица истории попыток. `user_task_progress` остаётся
сводкой (статус и счётчик попыток), а здесь хранится каждая засчитанная
отправка: код, результат по кейсам и время. Пробная проверка (S42-001)
попытку не засчитывает и в эту таблицу не пишется.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column(
            "passed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "passed_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "total_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "results",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_task_attempts_user_task",
        "task_attempts",
        ["user_id", "task_id", "created_at"],
    )
    op.create_index(
        "idx_task_attempts_task",
        "task_attempts",
        ["task_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_task_attempts_task", table_name="task_attempts")
    op.drop_index("idx_task_attempts_user_task", table_name="task_attempts")
    op.drop_table("task_attempts")
