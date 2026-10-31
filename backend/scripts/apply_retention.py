"""Retention-политика (S26-003) — CLI.

Логика — `app.services.retention.apply_retention`; здесь только аргументы и
вывод. Примеры:

    python backend/scripts/apply_retention.py --dry-run
    python backend/scripts/apply_retention.py
    python backend/scripts/apply_retention.py --only audit_log --batch-size 500
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.retention import TABLES, apply_retention  # noqa: E402


def _configure_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    _configure_output()
    parser = argparse.ArgumentParser(description="Retention-политика (S26-003)")
    parser.add_argument("--dry-run", action="store_true", help="только посчитать")
    parser.add_argument("--only", choices=[table.name for table in TABLES], default=None)
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args(argv)

    results = asyncio.run(
        apply_retention(
            dry_run=args.dry_run, only=args.only, batch_size=max(1, args.batch_size)
        )
    )

    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    print(f"retention {mode}:")
    for name, count in results.items():
        print(f"  {name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
