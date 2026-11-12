# Спринт 40 — DX & Docs

**Дата:** 2026-11-12
**Этап:** v0.6.0 «Production Hardening»
**Задачи:** S40-001…S40-005
**Статус:** завершён

---

## 1. Итоги

| Задача | Результат |
|--------|-----------|
| S40-001 | `docs/adr/` + ADR-001…007 (GHCR/digest, Caddy, trusted proxies/refresh, бэкапы, guardrails, `*_FILE`, CI-гейты) |
| S40-002 | `GETTING_STARTED.md` §2 — настройки v0.6.0; чек-лист/ссылки; полный онбординг на чистой машине — ручная проверка |
| S40-003 | `CONTRIBUTING.md`, `.github/CODEOWNERS`, issue-шаблоны bug/feature, PR-шаблон |
| S40-004 | `scripts/check_env_drift.py` + `test_env_drift.py`; `.env.example` = 76 полей; гейты/CI; негативный кейс проверен |
| S40-005 | README/ARCHITECTURE/docs-навигация/RELEASES/CHANGELOG; отчёты |

---

## 2. Файлы

**Новое:**
- `docs/adr/README.md`, `0001-ghcr-digest-deploy.md`, `0002-caddy-edge.md`,
  `0003-trusted-proxies-refresh-body.md`, `0004-backups-systemd-age-s3.md`,
  `0005-llm-guardrails.md`, `0006-secrets-file.md`, `0007-cicd-gates.md`;
- `CONTRIBUTING.md`;
- `.github/CODEOWNERS`, `.github/ISSUE_TEMPLATE/{bug,feature}.md`,
  `.github/pull_request_template.md`;
- `scripts/check_env_drift.py`;
- `backend/tests/test_env_drift.py`;
- `docs/reports/sprint-40/` (5 шагов + этот отчёт).

**Изменено:**
- `.env.example` — недостающие переменные `Settings`;
- `scripts/ci/gates.sh`, `gates.ps1`, `backend-lint.sh`;
- `.github/workflows/ci.yml`, `gitflic-ci.yaml`;
- `README.md`, `docs/README.md`, `docs/GETTING_STARTED.md`,
  `docs/ARCHITECTURE.md`, `docs/CHANGELOG.md`, `docs/RELEASES.md`,
  `TODO_V0.4.md`.

---

## 3. Проверки

```
python scripts/check_env_drift.py
# OK: Settings (76 полей) и .env.example согласованы

# негативный кейс: удалить RATE_LIMIT_ENABLED= → exit 1
# восстановить → exit 0

cd backend && pytest tests/test_env_drift.py -q
# 4 passed

cd backend && pytest -q --cov=app --cov-fail-under=70
# 834 passed, 1 skipped; coverage 79.17%

python -m ruff check scripts
# All checks passed

yaml.safe_load(ci.yml, ci-selfhosted.yml, perf-nightly.yml, gitflic-ci.yaml)
# OK

# локальные ссылки в 7 ключевых docs
# 0 missing
```

Дополнительно ранее в S39: `ruff`/`mypy` — чисто, `caddy validate` — OK,
`docker compose config` — OK.

---

## 4. Ограничения

- **Чистая машина:** полный онбординг без кэша образов/venv не прогонялся;
  документ актуализирован, но первый внешний участник должен пройти его и
  зафиксировать пробелы.
- **GitFlic:** `KI-023` — required checks/защита `main` включаются владельцем;
  скрипт и инструкция готовы, паритет базовых гейтов сохранён.
- **Perf baseline:** `measured: null` до первого nightly-прогона (S39).
- **LLM-модерация:** полная модерация ответов — `KI-036`, v0.7.0.

---

## 5. Следующий шаг

**S41 — Release v0.6.0:** `UPGRADE.md` (0.5.0 → 0.6.0), финальные релиз-ноты
`docs/releases/v0.6.0.md`, тег `v0.6.0`, приёмка и итог этапа
`docs/reports/v0.4.0/STAGE.md`.
