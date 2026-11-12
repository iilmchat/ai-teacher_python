# ADR-007 — CI-гейты, preflight и GitFlic merge-gate

**Статус:** Accepted (активация GitFlic — владелец)
**Дата:** 2026-11-12
**Контекст:** GitHub Free/private не даёт branch protection (KI-023), а
self-hosted runner может зависнуть в `queued`. Нужны быстрые красные статусы,
одинаковые проверки на GitHub и GitFlic и понятный ручной fallback.

## Решение

- **Preflight** (`scripts/ci/preflight.ps1`) — первый шаг каждого
  self-hosted job и release: Docker daemon, диск, workspace, файлы. Ошибка —
  красный статус за десятки секунд. Для GitFlic — `preflight.sh`.
- **Coverage-гейт:** backend `--cov-fail-under=70`; frontend
  `pnpm test:coverage` (пороги в `vite.config.ts`).
- **Паритет:** `scripts/ci/check_ci_parity.py` проверяет Lint/Test/Frontend/
  Security в обоих пайплайнах.
- **Локально:** `gates.sh`/`gates.ps1` (`--fast`/`--full`/`--json`),
  `make release-check`.
- **GitFlic merge-gate:** `scripts/ci/gitflic-gate.ps1` + инструкция
  `docs/CI.md` §14.2. Активация (MR-пайплайн, защита `main`, required
  pipeline status) требует доступа владельца — до этого KI-023 `In Progress`.
- **Env drift** (`scripts/check_env_drift.py`) — `.env.example` ↔ Settings.

## Последствия

**Плюсы:**
- сломанный runner даёт быстрый красный, а не «вечное» ожидание;
- одинаковые базовые проверки на GitHub/GitFlic;
- локальный прогон воспроизводит CI.

**Минусы/риски:**
- полностью offline runner всё равно остаётся `queued` (платформенное);
- required checks на GitHub Free недоступны — ручной гейт до Pro/GitFlic;
- preflight добавляет ~5–10 с на job (приемлемо).

**Ссылки:** `.github/workflows/ci-selfhosted.yml`, `gitflic-ci.yaml`,
`scripts/ci/preflight.*`, `scripts/ci/gates.*`, `docs/CI.md` §14–15.
