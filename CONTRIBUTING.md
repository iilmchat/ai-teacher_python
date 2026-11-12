# CONTRIBUTING.md — как участвовать в разработке

> Проект: AI Teacher for Python. Правила кода и окружения — `docs/RULES.md`,
> архитектура — `docs/ARCHITECTURE.md`, план — `TODO_V0.4.md`.
> Работаем с детскими данными: секреты и PII не коммитим.

---

## 1. Ветки и коммиты

- Ветка от `main`: `feat/<кратко>`, `fix/<кратко>`, `docs/<кратко>`.
- Один PR — одна логическая задача; крупные изменения — отдельными шагами.
- **Conventional Commits** (как в истории):
  - `feat(api): ...`, `fix(auth): ...`, `docs(security): ...`,
    `test(perf): ...`, `chore(ci): ...`;
  - тело — что и зачем, ссылки на `S<N>-NNN`/`KI-NNN`;
  - breaking change — `feat!:` или блок `BREAKING CHANGE:`.
- Коммит/пуш в `main` — только по зелёным гейтам и после ревью (RULES §10).
  Пока GitHub Free не даёт required checks, мерж — ручной (KI-023).

## 2. Локальные гейты

Единый прогон:

```bash
# Linux/macOS/Git Bash
bash scripts/ci/gates.sh --fast        # lint/mypy/typecheck/lint/unit
bash scripts/ci/gates.sh --full --ci   # + coverage/e2e/compose/promtool
bash scripts/ci/gates.sh --fast --json # gates-report.json

# Windows
pwsh -NoProfile -File scripts/ci/gates.ps1 -Fast
pwsh -NoProfile -File scripts/ci/gates.ps1 -Full -Json
```

`make release-check` = `gates --full --ci`.

Что именно проверяется:

| Шаг | Команда/скрипт |
|-----|----------------|
| image pins | `python backend/scripts/check_image_pins.py` |
| CI parity | `python scripts/ci/check_ci_parity.py` |
| env drift | `python scripts/check_env_drift.py` |
| backend lint | `cd backend && ruff check app tests scripts` |
| backend types | `cd backend && mypy app` |
| backend tests | `pytest -q --cov=app --cov-fail-under=70` |
| frontend | `pnpm typecheck && pnpm lint && pnpm test:coverage && pnpm build` |
| e2e | `pnpm e2e` (полный прогон) |
| compose/caddy/promtool | `compose config`, `caddy validate`, `promtool` |

**Preflight** в CI (`scripts/ci/preflight.*`) проверяет Docker/диск/workspace;
локально его можно запустить отдельно, если job падает до кода.

## 3. Тесты

- Backend: pytest на реальном PostgreSQL/pgvector + Redis (см. conftest).
  Новый код — с тестами; регресс-тест на баг обязателен.
- Frontend: vitest + Testing Library; e2e — Playwright.
- Контракт API: `tests/test_contract_openapi.py`; снапшот обновлять только
  осознанно (`python scripts/snapshot_openapi.py`).
- Миграции: `alembic upgrade head`, `alembic check`,
  `tests/test_migrations.py`.
- Query-count регрессии: `tests/test_query_counts.py` (не допускать N+1).

## 4. Env и секреты

- Локально: `cp .env.example .env`; новые поля `Settings` **обязаны** попасть
  в `.env.example` — иначе упадёт `check_env_drift.py`.
- Секреты (`SECRET_KEY`, `POSTGRES_PASSWORD`, `DEEPSEEK_API_KEY`) — только
  локально/в secrets; в коде и тестах — заглушки.
- Prod: `.env.prod` (gitignored) или `*_FILE`/Docker secrets
  (`deploy/docker-compose.secrets.example.yml`).
- Перед коммитом: `gitleaks git . --config .gitleaks.toml` (или CI Security).

## 5. Документация и отчёты

- Каждый шаг спринта — `docs/reports/sprint-N/STEP-MM_<ТЕМА>.md`
  (7 разделов по RULES §12); спринт — `SPRINT-N.md`.
- Обновляйте `docs/CHANGELOG.md`, `docs/RELEASES.md`, `KNOWN_ISSUES.md` при
  изменениях поведения/контракта.
- ADR для архитектурных решений — `docs/adr/` (шаблон в README).

## 6. PR

1. Опишите задачу, изменения, проверки (какие команды запускали).
2. Приложите отчёт шага (или ссылку).
3. Убедитесь, что CI зелёный; красный CI не мержим.
4. Не смешивайте рефакторинг и фичу без необходимости.
5. После мержа — удалите ветку; релизные теги ставит владелец/release workflow.
