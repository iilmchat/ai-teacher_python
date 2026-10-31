"""users.is_active для мягкого удаления аккаунта (S26-004)

Revision ID: 012
Revises: 011
Create Date: 2026-10-31

Аддитивная миграция: колонка `is_active` (по умолчанию true) — аккаунт,
удалённый пользователем, анонимизируется и не может войти; физическая чистка
(если потребуется) — вручную/по расписанию, см. docs/PRIVACY.md.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_active")
