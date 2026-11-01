"""Backfill эмбеддингов истории чата (S27-001) — CLI.

    python backend/scripts/backfill_embeddings.py --dry-run
    python backend/scripts/backfill_embeddings.py --batch-size 100 --limit 1000
    python backend/scripts/backfill_embeddings.py --sleep 0.3

Требует настроенного провайдера эмбеддингов (`RAG_ENABLED=true`,
`RAG_EMBEDDING_BASE_URL`). Без него скрипт завершается с кодом 2 и объяснением.
Запуск идемпотентен: уже обработанные сообщения повторно не считаются.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.db.database import async_session_factory  # noqa: E402
from app.services.backfill import backfill_embeddings, format_stats  # noqa: E402
from app.services.llm.embeddings import create_embedding_provider  # noqa: E402


def _configure_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


async def _run(args: argparse.Namespace) -> int:
    provider = create_embedding_provider()
    if provider is None:
        print(
            "Провайдер эмбеддингов не настроен: включите RAG_ENABLED=true и задайте "
            "RAG_EMBEDDING_BASE_URL (см. .env.example).",
            file=sys.stderr,
        )
        return 2

    async with async_session_factory() as db:
        stats = await backfill_embeddings(
            db,
            provider,
            batch_size=args.batch_size,
            limit=args.limit,
            dry_run=args.dry_run,
            sleep_s=args.sleep,
        )

    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    print(f"backfill {mode} (model={settings.rag_embedding_model}): {format_stats(stats)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    _configure_output()
    parser = argparse.ArgumentParser(description="Backfill эмбеддингов (S27-001)")
    parser.add_argument("--dry-run", action="store_true", help="посчитать без записи")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--limit", type=int, default=None, help="максимум сообщений")
    parser.add_argument("--sleep", type=float, default=0.0, help="пауза между батчами, с")
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
