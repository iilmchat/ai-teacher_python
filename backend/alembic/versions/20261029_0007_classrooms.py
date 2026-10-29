"""classrooms and assignments

Revision ID: 007
Revises: 006
Create Date: 2026-10-29

Классы, участники и назначения задач (S16-001).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "classrooms",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("join_code", sa.String(12), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("join_code"),
    )
    op.create_index("idx_classrooms_owner", "classrooms", ["owner_id"])

    op.create_table(
        "classroom_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("classroom_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="student"),
        sa.Column(
            "joined_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["classroom_id"], ["classrooms.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "classroom_id", "user_id", name="uq_classroom_member"
        ),
    )
    op.create_index(
        "idx_classroom_members_user", "classroom_members", ["user_id"]
    )

    op.create_table(
        "assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("classroom_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["classroom_id"], ["classrooms.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("classroom_id", "task_id", name="uq_assignment_task"),
    )
    op.create_index("idx_assignments_classroom", "assignments", ["classroom_id"])


def downgrade() -> None:
    op.drop_index("idx_assignments_classroom", table_name="assignments")
    op.drop_table("assignments")
    op.drop_index("idx_classroom_members_user", table_name="classroom_members")
    op.drop_table("classroom_members")
    op.drop_index("idx_classrooms_owner", table_name="classrooms")
    op.drop_table("classrooms")
