"""audit log для действий teacher/admin (S25-004)

Revision ID: 011
Revises: 010
Create Date: 2026-10-31

Аддитивная миграция: новая таблица `audit_log` + индексы. `actor_id` —
nullable с `ON DELETE SET NULL`: удаление пользователя не должно стирать
историю действий (но и не должно каскадно удалять журнал).

Downgrade удаляет только эту таблицу (RULES §11.5).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_role", sa.String(length=30), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_log_created", "audit_log", ["created_at"])
    op.create_index(
        "idx_audit_log_action_created", "audit_log", ["action", "created_at"]
    )
    op.create_index(
        "idx_audit_log_actor_created", "audit_log", ["actor_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_audit_log_actor_created", table_name="audit_log")
    op.drop_index("idx_audit_log_action_created", table_name="audit_log")
    op.drop_index("idx_audit_log_created", table_name="audit_log")
    op.drop_table("audit_log")
