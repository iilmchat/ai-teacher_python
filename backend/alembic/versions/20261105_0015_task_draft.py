"""draft_code в user_task_progress — автосохранение черновика (S42-003)

Revision ID: 015
Revises: 014
Create Date: 2026-11-05

Аддитивная миграция: две nullable-колонки для хранения незавершённого кода
ученика между сессиями. `draft_code` — сам черновик, `draft_updated_at` —
когда он сохранён (для индикатора в интерфейсе).

Черновик не является решением: он не попадает в историю попыток
(`task_attempts`) и не влияет на счётчик попыток или статус задачи.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_task_progress", sa.Column("draft_code", sa.Text(), nullable=True))
    op.add_column(
        "user_task_progress", sa.Column("draft_updated_at", sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("user_task_progress", "draft_updated_at")
    op.drop_column("user_task_progress", "draft_code")
