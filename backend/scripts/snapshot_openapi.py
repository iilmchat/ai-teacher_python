"""Снапшот OpenAPI и проверка совместимости (S22-001).

Зачем: апгрейды зависимостей (`fastapi`/`starlette`, S22-002) не должны молча
менять контракт API. Снапшот `tests/contracts/openapi.json` фиксирует схему,
а тест `tests/test_contract_openapi.py` разрешает только аддитивные изменения
(новые пути/поля/значения enum) и падает на любом breaking-изменении
(удалённый путь/операция/поле, смена типа, новый обязательный ввод).

Использование (из `backend/`):

    python scripts/snapshot_openapi.py            # обновить снапшот
    python scripts/snapshot_openapi.py --check    # проверить (exit 1 при breaking)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = BACKEND_ROOT / "tests" / "contracts" / "openapi.json"

sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402  # приложение нужно импортировать после sys.path


def build_spec() -> dict[str, Any]:
    """Схема OpenAPI текущего приложения."""
    spec: dict[str, Any] = app.openapi()
    return spec


def dump_spec(spec: dict[str, Any], path: Path) -> None:
    """Записать снапшот в стабильном виде (сортировка ключей, UTF-8)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8")


def load_spec(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Снапшот OpenAPI (S22-001)")
    parser.add_argument("--output", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Не писать файл, а проверить совместимость (exit 1 при breaking)",
    )
    args = parser.parse_args(argv)

    spec = build_spec()

    if not args.check:
        dump_spec(spec, args.output)
        print(f"Снапшот записан: {args.output}")
        return 0

    if not args.output.is_file():
        print(f"Снапшот не найден: {args.output}", file=sys.stderr)
        return 2

    from tests.contract_utils import diff_openapi

    problems = diff_openapi(load_spec(args.output), spec)
    if problems:
        print(f"Breaking-изменения контракта ({len(problems)}):")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("Контракт совместим со снапшотом (только аддитивные изменения)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
