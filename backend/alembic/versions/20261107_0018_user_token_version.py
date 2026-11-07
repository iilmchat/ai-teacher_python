"""Версия refresh-токенов пользователя — token_version (S45-001)

Revision ID: 018
Revises: 017
Create Date: 2026-11-07

Аддитивная миграция: целочисленный счётчик в `users`. Смена пароля
увеличивает его на 1; refresh-токены, выданные до смены, при обновлении
проверяют `tv` в payload и отклоняются (KI-028). Access-токены остаются
короткоживущими и версию не учитывают (принятое решение, KI-027).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
