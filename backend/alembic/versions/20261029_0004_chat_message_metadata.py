"""chat message metadata

Revision ID: 004
Revises: 003
Create Date: 2026-10-29

Добавляет `chat_messages.metadata` (JSONB): провайдер, модель и версия
промпта для каждого ответа ассистента (S12-006), а также предупреждения
политики уровня (S12-005).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "metadata")
