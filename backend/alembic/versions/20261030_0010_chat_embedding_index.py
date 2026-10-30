"""chat embedding column guard and hnsw index

Revision ID: 010
Revises: 009
Create Date: 2026-10-30

Колонка `chat_messages.embedding VECTOR(1536)` появилась ещё в миграции 001
(она входила в базовую схему чата). Здесь S19-005 добавляет индекс для
семантического поиска и страхует колонку `ADD COLUMN IF NOT EXISTS` — если
схема развёрнута из старой ветки без этой колонки, поиск всё равно заработает.

- HNSW + `vector_cosine_ops`: pgvector 0.8.x (образ `pgvector/pgvector:pg17`)
  поддерживает HNSW; косинусное расстояние совпадает с `cosine_distance()`
  в SQLAlchemy.
- Расширение `vector` в downgrade **не** удаляется (RULES §11.4): им могут
  пользоваться другие объекты. Колонка тоже остаётся — она создана не здесь.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Колонка могла быть создана миграцией 001; IF NOT EXISTS делает шаг идемпотентным
    op.execute(
        "ALTER TABLE chat_messages "
        "ADD COLUMN IF NOT EXISTS embedding vector(1536)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chat_messages_embedding_hnsw "
        "ON chat_messages USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    # Только индекс: колонка и расширение vector существовали до этой миграции
    op.execute("DROP INDEX IF EXISTS idx_chat_messages_embedding_hnsw")
