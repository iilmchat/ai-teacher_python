"""tasks and user progress

Revision ID: 003
Revises: 002
Create Date: 2026-10-29

Создаёт задачи (tasks) и прогресс учеников (user_task_progress).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE taskdifficulty AS ENUM ('easy', 'medium', 'hard')")
    op.execute(
        "CREATE TYPE taskstatus AS ENUM ('not_started', 'in_progress', 'completed')"
    )

    task_difficulty = postgresql.ENUM(
        "easy", "medium", "hard", name="taskdifficulty", create_type=False
    )
    task_status = postgresql.ENUM(
        "not_started",
        "in_progress",
        "completed",
        name="taskstatus",
        create_type=False,
    )

    op.create_table(
        "tasks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "difficulty",
            task_difficulty,
            nullable=False,
            server_default="easy",
        ),
        sa.Column("category", sa.String(100), nullable=False, server_default="general"),
        sa.Column(
            "test_cases",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "hints",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("solution_template", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_tasks_difficulty", "tasks", ["difficulty"])
    op.create_index("idx_tasks_category", "tasks", ["category"])

    op.create_table(
        "user_task_progress",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            task_status,
            nullable=False,
            server_default="not_started",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("best_solution", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "task_id", name="uq_progress_user_task"),
    )
    op.create_index("idx_progress_user", "user_task_progress", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_progress_user", table_name="user_task_progress")
    op.drop_table("user_task_progress")

    op.drop_index("idx_tasks_category", table_name="tasks")
    op.drop_index("idx_tasks_difficulty", table_name="tasks")
    op.drop_table("tasks")

    op.execute("DROP TYPE IF EXISTS taskstatus")
    op.execute("DROP TYPE IF EXISTS taskdifficulty")
