"""task tags

Revision ID: 005
Revises: 004
Create Date: 2026-10-29

Добавляет `tasks.tags` (JSONB) и GIN-индекс для поиска по тегам (S14-004).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_index(
        "idx_tasks_tags", "tasks", ["tags"], postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_index("idx_tasks_tags", table_name="tasks")
    op.drop_column("tasks", "tags")
