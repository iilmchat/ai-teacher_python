"""achievements and notifications

Revision ID: 008
Revises: 007
Create Date: 2026-10-30

Достижения, полученные достижения и in-app уведомления (S17-001, S17-004).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACHIEVEMENTS = [
    ("first_task", "Первая задача", "Решена первая задача", "🚀"),
    ("ten_tasks", "Десятка", "Решено десять задач", "🔟"),
    ("streak_3", "Три дня подряд", "Занятия три дня подряд", "🔥"),
    ("all_easy", "Лёгкая серия", "Решены все лёгкие задачи", "🟢"),
    ("all_medium", "Средняя серия", "Решены все средние задачи", "🟡"),
    ("all_hard", "Сложная серия", "Решены все сложные задачи", "🔴"),
]


def upgrade() -> None:
    op.create_table(
        "achievements",
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("icon", sa.String(10), nullable=False, server_default="🏆"),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "user_achievements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column(
            "earned_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["code"], ["achievements.code"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "code", name="uq_user_achievement"),
    )
    op.create_index("idx_user_achievements_user", "user_achievements", ["user_id"])

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_notifications_user", "notifications", ["user_id"])
    op.create_index(
        "idx_notifications_unread", "notifications", ["user_id", "read_at"]
    )

    achievements_table = sa.table(
        "achievements",
        sa.column("code", sa.String),
        sa.column("title", sa.String),
        sa.column("description", sa.String),
        sa.column("icon", sa.String),
    )
    op.bulk_insert(
        achievements_table,
        [
            {"code": code, "title": title, "description": desc, "icon": icon}
            for code, title, desc, icon in ACHIEVEMENTS
        ],
    )


def downgrade() -> None:
    op.drop_index("idx_notifications_unread", table_name="notifications")
    op.drop_index("idx_notifications_user", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(
        "idx_user_achievements_user", table_name="user_achievements"
    )
    op.drop_table("user_achievements")
    op.drop_table("achievements")
