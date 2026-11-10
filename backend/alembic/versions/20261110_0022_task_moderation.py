"""Модерация задач — source и moderation_comment (S47-003).

Revision ID: 022
Revises: 021
Create Date: 2026-11-10

Аддитивная миграция: у задачи появляется происхождение (`manual` для уже
существующих задач) и комментарий модератора при возврате в доработку.
Индекс обслуживает очередь модерации (source) и её сортировку по дате.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "source",
            sa.String(length=20),
            server_default="manual",
            nullable=False,
        ),
    )
    op.add_column(
        "tasks",
        sa.Column("moderation_comment", sa.Text(), nullable=True),
    )
    op.create_index(
        "idx_tasks_source_created",
        "tasks",
        ["source", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_tasks_source_created", table_name="tasks")
    op.drop_column("tasks", "moderation_comment")
    op.drop_column("tasks", "source")
