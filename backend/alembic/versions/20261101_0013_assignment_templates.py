"""assignment_templates для шаблонов назначений (S28-002)

Revision ID: 013
Revises: 012
Create Date: 2026-11-01

Аддитивная миграция: таблица шаблонов учителя. `task_ids` — JSONB-массив
UUID-строк: шаблон не держит FK на задачи, чтобы удаление задачи не рвало
шаблон; при применении отсутствующие задачи пропускаются (skipped).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assignment_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "task_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_assignment_templates_owner",
        "assignment_templates",
        ["owner_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_assignment_templates_owner", table_name="assignment_templates")
    op.drop_table("assignment_templates")
