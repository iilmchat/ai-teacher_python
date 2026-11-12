"""Проверка Grafana-дашбордов как JSON (S35-004).

Запускается локально и в CI; не требует Grafana. Проверяет:
- файл — валидный JSON;
- есть title, uid, непустой список panels;
- у каждой панели есть type/title и хотя бы один target с expr.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DASHBOARDS = ROOT / "deploy" / "monitoring" / "grafana" / "dashboards"


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{path.name}: invalid JSON: {exc}"]

    if not data.get("title"):
        errors.append(f"{path.name}: отсутствует title")
    if not data.get("uid"):
        errors.append(f"{path.name}: отсутствует uid")

    panels = data.get("panels")
    if not isinstance(panels, list) or not panels:
        return errors + [f"{path.name}: нет panels"]

    for index, panel in enumerate(panels):
        where = f"{path.name}: panel[{index}]"
        if not panel.get("type"):
            errors.append(f"{where}: нет type")
        if not panel.get("title"):
            errors.append(f"{where}: нет title")
        targets = panel.get("targets") or []
        if not any(str(target.get("expr", "")).strip() for target in targets):
            errors.append(f"{where}: нет target с expr")
    return errors


def main() -> int:
    files = sorted(DASHBOARDS.glob("*.json"))
    if not files:
        print(f"ERROR: дашборды не найдены в {DASHBOARDS}", file=sys.stderr)
        return 1

    errors: list[str] = []
    for path in files:
        errors.extend(validate(path))

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"OK: {len(files)} dashboard(s) валидны: {', '.join(p.name for p in files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
