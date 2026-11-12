# Спринт 41 — Release v0.6.0

**Дата:** 2026-11-12
**Этап:** v0.6.0 «Production Hardening» (финальный)
**Задачи:** S41-001…S41-005
**Статус:** релиз подготовлен; тег `v0.6.0` — после утверждения владельцем

---

## 1. Задача

Подготовить воспроизводимый релиз v0.6.0: синхронизировать версии, оформить
релиз-ноты/UPGRADE, прогнать полные гейты, проверить откат и зафиксировать
итог этапа. Тег и публикацию не выполнять до утверждения владельцем.

---

## 2. Что сделано

### Версии и артефакты (S41-001/002)

- Версия `0.6.0` уже синхронизирована в `pyproject.toml`,
  `frontend/package.json`, `backend/app/config.py`;
  `python backend/scripts/check_version.py --strict` — 0 расхождений.
- `docs/UPGRADE.md` актуализирован: v0.5.0 → v0.6.0, **новых миграций нет**
  (head `022`), ENV S34–S40, breaking refresh, GHCR/Caddy-деплой, откат,
  restore, лимиты S39.
- `docs/releases/v0.6.0.md` — релиз-ноты: закрытые блокеры аудита, готовность
  к **закрытому пилоту single-node**, публичный production — нет, ссылки на
  ADR/RUNBOOK/UPGRADE.
- `docs/CHANGELOG.md`, `docs/RELEASES.md` (спринт 41 + итог этапа),
  README/docs README — версия/статус/ссылки.

### Гейты и откат (S41-003)

- `bash scripts/ci/gates.sh --full --ci`: env-drift, image-pins, CI parity,
  ruff, mypy, backend coverage, frontend typecheck/lint/unit/build, compose,
  promtool, e2e — см. §3.
- `python -m alembic current` → `022 (head)`;
  `alembic check` → `No new upgrade operations detected`.
- `scripts/rollback.sh --dry-run` на изолированных временных `.env.prod` и
  `.last_deploy` (digest-ссылки): план отката выведен, `compose config` OK,
  `DRY-RUN: откат не выполнялся`, exit **0**. Репозиторий не изменялся.
- GHCR-сборка, SBOM/provenance, staging-деплой и реальный restore drill — не
  выполнялись: требуют тега/approval и staging-контура (см. §4).
- По итогам первого полного прогона исправлены два локальных блокера:
  promtool неверно монтировал путь в Git Bash на Windows
  (`scripts/monitoring/validate_prometheus.sh`), а e2e не передавал
  `SECRET_KEY` при `DEBUG=false` (`frontend/playwright.config.ts`).

### Отчёты (S41-005)

- `docs/reports/sprint-41/SPRINT-41.md` (этот файл).
- `docs/reports/v0.4.0/STAGE.md` — итог этапа: метрики, отклонения, KI, уроки.

---

## 3. Проверки

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Версии | `python backend/scripts/check_version.py --strict` | OK: `0.6.0` во всех трёх источниках |
| Env-drift | `python scripts/check_env_drift.py` | OK: 76 полей |
| Backend lint/types | `ruff check app tests scripts` / `mypy app` | All checks passed / 0 issues (104 файла) |
| Backend tests | `pytest -q --cov=app --cov-fail-under=70` | **834 passed, 1 skipped**, coverage **79.17%** |
| Frontend typecheck/lint | `pnpm typecheck` / `pnpm lint` | OK |
| Frontend unit | `pnpm test` | **279 passed** (47 файлов) |
| Frontend build | `pnpm build` | OK |
| E2E | `pnpm e2e` (Playwright) | **37 passed, 1 skipped** (2.7 мин) |
| Compose/Caddy | `compose config`, `caddy validate` | OK / Valid configuration |
| Prometheus | `promtool` | OK |
| Миграции | `alembic current` / `check` | `022 (head)` / no new operations |
| Откат | `scripts/rollback.sh --dry-run` | exit 0, план на digest |
| Полные гейты | `gates.sh --full --ci` | **OK: 13/13 шагов** (env-drift, lint, mypy, backend/frontend coverage, build, compose, promtool, e2e) |

---

## 4. Риски и ограничения

1. **Тег не создан** — по требованию владельца. После approval: тег `v0.6.0`
   запускает `docker-publish.yml` (GHCR, SBOM/provenance, digest artifact), затем
   GitHub/GitFlic Release и post-release smoke.
2. **Staging-деплой и реальный откат** не выполнялись: нет staging-контура;
   проверен dry-run и compose-валидация. Риск — обнаружится только на стенде.
3. **SBOM/checksums:** SBOM/provenance встроены в publish; отдельный файл
   checksums не формируется (в S33 это осталось отклонением).
4. **Perf baseline** ждёт nightly-runner (`measured: null`).
5. **Публичный production** не разрешён: нужны отдельный VPS/домен, 152-ФЗ,
   multi-node/HA, e-mail-восстановление и полная LLM-модерация.

---

## 5. Проблемы и открытия

- `KI-023` — required checks GitHub Free/GitFlic активирует владелец.
- `KI-035`/`KI-036` — e-mail и полная модерация LLM остаются на v0.7.0.
- `KI-027` — access-токен не отзывается (httpOnly/BFF — v0.7.0).
- Новых блокирующих проблем в S41 не найдено. В первом полном прогоне
  проявились две среды/конфигурации: promtool mount path на Windows и
  отсутствие `SECRET_KEY` в e2e — исправлены до повторного прогона.
- Во втором прогоне: разовый `WinError 121` при setup `test_rag_search`
  (TCP-таймаут, тест изолированно зелёный — 11 passed) и занятый порт `3100`
  посторонним контейнером `sw-api-lean` (внешняя среда). Финальный прогон —
  на свободных портах `3110/8010`; в CI используются штатные `3100/8001`.

---

## 6. Дальнейшие шаги

1. Владелец утверждает релиз-ноты и тег `v0.6.0`.
2. Создать тег `v0.6.0` → дождаться GHCR publish (3 образа + digest artifact).
3. Зафиксировать digest в `.env.prod`, задеплоить на staging/пилот по RUNBOOK.
4. Post-release smoke: `/health/ready`, `/api/v1/health` (`version: 0.6.0`),
   HTTPS-домен, refresh через тело, бэкап/restore drill.
5. Создать GitHub/GitFlic Release из `docs/releases/v0.6.0.md`; приложить
   digest/SBOM-артефакты.
6. Перейти к v0.7.0 ([TODO_V0.7.md](../../../TODO_V0.7.md)).

---

## 7. Итог шага

Кодовая часть релиза v0.6.0 завершена: версии синхронизированы, документация и
релиз-ноты готовы, полные гейты и dry-run отката зелёные. Остались действия
владельца: утверждение, тег, публикация образов/релизов и post-release smoke.
