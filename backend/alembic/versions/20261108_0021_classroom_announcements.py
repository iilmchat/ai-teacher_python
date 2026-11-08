"""Объявления класса — classroom_announcements (S46-006).

Revision ID: 021
Revises: 020
Create Date: 2026-11-08

Аддитивная миграция: объявления публикует учитель, видят все участники
класса. Удаляются вместе с классом или автором.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "classroom_announcements",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "classroom_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "author_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["classroom_id"],
            ["classrooms.id"],
            name="classroom_announcements_classroom_id_fkey",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name="classroom_announcements_author_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="classroom_announcements_pkey"),
    )
    op.create_index(
        "idx_classroom_announcements_classroom",
        "classroom_announcements",
        ["classroom_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_classroom_announcements_classroom",
        table_name="classroom_announcements",
    )
    op.drop_table("classroom_announcements")
