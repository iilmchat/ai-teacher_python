# S37-006 — документация и закрытие

**Дата:** 2026-11-12
**Спринт:** 37
**Статус:** завершено (активация GitFlic — владелец)

## Обновлено

- `docs/CI.md`:
  - §10.3 — GitFlic-гейт, скрипт, статус `KI-023`;
  - §14 — preflight, merge-gate runbook, «если CI упал»;
  - §15 — coverage-гейты и таблица паритета.
- `docs/KNOWN_ISSUES.md` — `KI-023` → **In Progress** (готово: preflight,
  GitFlic-gate скрипт/инструкция, паритет; осталось: активация владельцем и
  красный тестовый MR).
- `docs/CHANGELOG.md`, `docs/RELEASES.md`, `TODO_V0.4.md` — статус S37.
- `.github/workflows/ci-selfhosted.yml` — preflight в каждом job + parity gate.
- `.github/workflows/ci.yml` — coverage 70%, frontend coverage, parity.
- `.github/workflows/release.yml` — preflight перед тегом/релизом.
- `gitflic-ci.yaml` — preflight, parity, image pins, i18n, coverage.
- `backend/tests/test_ci_config.py` — 8 тестов конфигурации.
- `scripts/ci/preflight.{ps1,sh}`, `gates.{ps1,sh}`,
  `gitflic-gate.ps1`, `check_ci_parity.py`, `Makefile`.

## Итог

Инженерная часть спринта закрыта: preflight, coverage, паритет, локальные
гейты. Merge-gate GitFlic подготовлен, но **не активирован** без доступа
владельца — `KI-023` остаётся `In Progress`. Это не имитация: закрытие
возможно только после красного тестового MR в GitFlic.
