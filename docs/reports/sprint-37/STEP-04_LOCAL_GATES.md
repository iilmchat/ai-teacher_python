# S37-005 — единый локальный прогон гейтов

**Дата:** 2026-11-12
**Спринт:** 37
**Статус:** завершено

## Скрипты

- `scripts/ci/gates.sh`:
  - `--fast` — image pins, parity, ruff, mypy, frontend typecheck/lint/unit;
  - `--full` — + backend pytest с coverage 70%, frontend coverage/build,
    compose config, promtool, e2e;
  - `--ci` — без интерактива; `--json` → `gates-report.json` (gitignored);
  - не останавливается на первом падении, возвращает 1 при любом красном шаге.
- `scripts/ci/gates.ps1` — то же для Windows/PowerShell.
- `Makefile`: `make gates-fast`, `make gates-full`, `make release-check`.

## Проверка

```
bash scripts/ci/gates.sh --fast --json
=== gates summary (fast) ===
  image-pins           ok       0s
  ci-parity            ok       1s
  backend-lint         ok       0s
  backend-mypy         ok       4s
  frontend-typecheck   ok       9s
  frontend-lint        ok       50s
  frontend-unit        ok       24s
OK: все гейты зелёные

gates-report.json: mode=fast, ok=true
```

`--full` требует поднятых PostgreSQL/Redis и Playwright — на машине разработки
запускается по необходимости; CI использует те же команды через
`scripts/ci/*.sh` и parity-тест.
