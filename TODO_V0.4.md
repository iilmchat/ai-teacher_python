# TODO_V0.4.md — план разработки v0.4.0 «Production & Multi-node»

> Четвёртый этап. Продолжение [TODO_V0.3.md](TODO_V0.3.md) (v0.3.x «Ops & Scale»).
> Правила — [docs/RULES.md](docs/RULES.md), контракты — [docs/SPEC.md](docs/SPEC.md),
> реестр проблем — [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md).

**Целевая версия:** v0.4.0  
**Создан:** 2026-11-02  
**Базис:** v0.3.2 + патч KI-024/KI-026  
**Статус:** планирование

---

## 0. Цель этапа

v0.3.x сделал продукт эксплуатируемым на одном узле. v0.4.0 делает его
**промышленным**: несколько реплик без общих точек отказа, наблюдаемость с
дашбордами и алертами как кодом, воспроизводимые деплой/бэкапы/откаты,
управляемая цепочка поставки и закрытый merge-gate.

Принципы этапа:

1. **Сначала измеримость, потом масштаб.** Ни один переход на N реплик не
   начинается без дашбордов, алертов и SLO из спринта 33.
2. **Автоматизация вместо памяти.** Бэкап, откат, миграции, релиз — команды,
   а не чек-лист «помню, как делал».
3. **Каждый gate воспроизводится локально.** Если проверку нельзя запустить
   одной командой, она не гейт, а пожелание.

---

## 1. Что не так с инженерной практикой (аудит v0.3.2)

Оценка по чек-листу зрелой production-практики. `✅` — есть, `⚠️` — частично,
`❌` — нет.

| Практика | Статус | Комментарий | Приоритет |
|----------|--------|-------------|-----------|
| Лицензия и юридическая определённость | ✅ (v0.3.2) | `LICENSE` (MIT) добавлен; в `pyproject.toml` — `license` | — |
| Политика безопасности (SECURITY.md) | ✅ (v0.3.2) | контакт, SLA, скоуп, процесс | — |
| Merge-gate (required checks) | ❌ | `KI-023`: GitHub Free не даёт branch protection; нужен GitFlic MR-гейт или Pro | P0 |
| Dependabot-долг | ⚠️ | 15 открытых PR, авто-мержа нет (заблокирован `KI-023`) | P0 |
| Пиннинг образов по digest, сканирование образов | ❌ | `FROM python:3.12-slim` без digest; нет trivy/hadolint | P0 |
| Non-root в Dockerfile | ❌ | нет `USER`; песочница изолирована, API — нет | P0 |
| Бэкапы: расписание, off-site, проверка восстановления | ⚠️ | `scripts/backup.sh`/`restore.sh` есть, расписания и off-site нет | P0 |
| Трейсинг и алерты как код | ❌ | структурированные логи есть, OTel нет; алерты только текстом в `DESIGN_ADMIN_AND_OPS` §10 | P1 |
| Дашборды Grafana в репозитории | ❌ | мониторинг описан, конфигов нет | P1 |
| Покрытие тестами как гейт | ⚠️ | `fail_under = 70` в `pyproject.toml`, но CI `pytest -q` без `--cov` | P1 |
| Pre-commit / локальные хуки | ❌ | гейты только в CI и вручную | P1 |
| Zero-downtime деплой и откат | ❌ | `docker compose up -d`, миграции в entrypoint | P1 |
| Чек-лист совместимости API/депрекаций | ⚠️ | `/api/v1`, контрактные тесты, но политики депрекации нет | P2 |
| SLO/бюджеты ошибок | ❌ | есть нефункциональные требования, SLO не сформулированы | P2 |
| Feature flags | ❌ | флаги ENV есть, механизма включения на пользователя нет | P2 |
| Мультиреплика: WS, метрики, планировщики | ⚠️ | метрики (`MULTIPROCESS`), retention (advisory lock) готовы; WS — нет | P1 |

**Не является проблемой (сделано и подтверждено):** структурированные логи и
request-id, `/health/live|ready`, retention, экспорт ПДн, a11y/i18n-аудит,
контрактные тесты OpenAPI, e2e Playwright, gitleaks, pip-audit/pnpm audit,
perf-smoke, миграционные тесты, `alembic check`.

---

## 2. Спринт 32 (патч v0.3.2) — закрыт

| Задача | Статус |
|--------|--------|
| KI-024: метрики-события + multiprocess-экспортёр | ✅ |
| KI-025: встроенный планировщик retention (advisory-лок) | ✅ |
| KI-026: `is_active` в login/refresh, bcrypt в потоке, guard `SECRET_KEY`, маскирование email в логах | ✅ |
| `app_build_info`, метрики `retention_*` | ✅ |
| `LICENSE`, `SECURITY.md`, `TODO_V0.4.md` | ✅ |
| Удалены мёртвые зависимости `aioredis`, `testcontainers` | ✅ |
| Тесты: `test_metrics_export.py`, `test_scheduler.py`, `test_auth.py` (+3) | ✅ |
| Документация: `CHANGELOG`, `KNOWN_ISSUES`, `DESIGN_ADMIN_AND_OPS`, `UPGRADE` | ✅ |

**Осталось в v0.3.2 (кандидаты):** расписание/off-site бэкапов, digest-пиннинг
образов, non-root `USER` в backend-образе, coverage-гейт (`--cov-fail-under`).

---

## 3. Спринты 33–41 (v0.4.0)

### Спринт 33: Supply chain & Repo hygiene — `[ ]`

**Цель:** воспроизводимые образы и управляемые зависимости.

- [ ] Пиннинг базовых образов по digest (`python:3.12-slim@sha256:…`, `node`, `pgvector`, `nginx`)
- [ ] `trivy` в CI: HIGH/CRITICAL в образе → fail; `hadolint` для Dockerfile
- [ ] SBOM (CycloneDX) как артефакт релиза
- [ ] Non-root `USER app` в `backend/Dockerfile` (с проверкой записи в `/tmp`)
- [ ] Политика Dependabot: группировка minor/patch, авто-мерж после зелёного CI
- [ ] Разбор 15 открытых PR (или явное закрытие с обоснованием)
- [ ] `pre-commit`: ruff, gitleaks, i18n-аудит, `check_version`
- [ ] `Makefile`/`task` — единые команды `lint/test/e2e/docker/release`
- **DoD:** образ собирается воспроизводимо, скан чист, локальные хуки = CI-гейты.

### Спринт 34: Observability 2.0 — `[ ]`

- [ ] OpenTelemetry (traces) для HTTP + LLM-вызовов, экспорт OTLP
- [ ] `deploy/monitoring/`: prometheus.yml, alert rules (as code), Grafana-дашборды
- [ ] Алерты: 5xx, p95, LLM-ошибки, sandbox-таймауты, retention-ошибки, пул БД
- [ ] SLO-документ: доступность, p95 API, доля успешных LLM-ответов
- [ ] Логи: конфиг Loki/Promtail (или ротация + `docker logs` → файлы)
- **DoD:** дашборд и алерты поднимаются из репозитория одной командой; есть SLO.

### Спринт 35: Multi-node readiness — `[ ]`

- [ ] WS: несколько реплик (Redis pub/sub или sticky sessions в nginx), тест на 2 инстанса
- [ ] Метрики: проверка multiprocess на `--workers 4` (интеграционный тест)
- [ ] Rate limit и кэш: проверить семанику при N репликах
- [ ] Фоновые задачи: единый список (retention, уведомления) — все через advisory-lock
- [ ] Nginx: upstream с 2 backend, healthcheck, `X-Forwarded-For`, лимиты
- **DoD:** 2 реплики проходят e2e и smoke без деградации; метрики суммируются.

### Спринт 36: Deploy, Backup & DR — `[ ]`

- [ ] Zero-downtime: rolling restart, миграции отдельным job'ом (`SKIP_MIGRATIONS`)
- [ ] Скрипт `scripts/deploy.ps1|sh`: сборка → миграции → rollout → health-gate → откат
- [ ] Бэкапы: systemd timer/cron, retention дампов, off-site (rsync/S3-совместимое)
- [ ] Проверка восстановления (restore drill) как автоматический тест
- [ ] Runbook инцидентов: БД недоступна, Redis, LLM, песочница, диск
- **DoD:** откат на предыдущую версию — одна команда; восстановление проверено.

### Спринт 37: CI Gates & GitFlic — `[ ]`

- [ ] Закрыть `KI-023`: GitFlic-агент, MR-пайплайн, «проверять статус последнего конвейера» = required
- [ ] GitHub → GitFlic зеркало и паритет job'ов (8/8)
- [ ] Coverage-гейт (`--cov-fail-under`) + отчёт в PR
- [ ] Таймауты и параллелизм CI, кэш зависимостей (pip/pnpm/npm)
- [ ] Единый `scripts/ci/gates.ps1|sh` для локального прогона всех гейтов
- **DoD:** красный PR физически не мержится; все гейты воспроизводимы локально.

### Спринт 38: Security & Privacy — `[ ]`

- [ ] Инвентаризация PII и DPIA (`docs/PRIVACY.md` → приложение)
- [ ] Секреты: вынос `SECRET_KEY`/ключей LLM в секрет-хранилище (Vault/Secrets Manager)
- [ ] JWT: rotation refresh-токенов, отзыв при смене пароля (проверить)
- [ ] CSP/security headers в nginx, HSTS при TLS
- [ ] Пентест-чеклист OWASP ASVS L1 для API
- **DoD:** чеклист ASVS L1 пройден, секретов в конфигах нет.

### Спринт 39: Performance & Capacity — `[ ]`

- [ ] Нагрузочный тест в CI (nightly) с порогами p95/RPS, отчёт-артефакт
- [ ] Аудит N+1 (SQLAlchemy `echo`/`pg_stat_statements`), недостающие индексы
- [ ] Кэш: hit-rate цель, инвалидация по тегам
- [ ] Размер БД и рост таблиц: прогноз, retention-политика в цифрах
- **DoD:** известна ёмкость узла (RPS, задержки), регресс ловится nightly.

### Спринт 40: DX & Docs — `[ ]`

- [ ] ADR: формат и первые 5 решений (CI-платформа, песочница, метрики, БД, лицензия)
- [ ] Онбординг с нуля: `docs/GETTING_STARTED.md` проверен на чистой машине
- [ ] `CONTRIBUTING.md`, `CODEOWNERS`, шаблоны issue/PR
- [ ] Сверка `.env.example` ↔ `Settings` в тесте (автодетект дрейфа)
- **DoD:** новый разработчик поднимает проект по docs без вопросов; дрейф конфига ловится тестом.

### Спринт 41: Release v0.4.0 — `[ ]`

- [ ] Полные гейты, `UPGRADE.md` (0.3.x → 0.4.0), миграции (если есть)
- [ ] Версия 0.4.0, тег, GitHub Release + GitFlic Release
- **DoD:** релиз воспроизводим, откат проверен, документация обновлена.

---

## 4. Кандидаты в KNOWN_ISSUES

Новые проблемы заводим сразу с `KI-NNN` (следующий свободный — **KI-028**).
Кандидаты: отсутствие tracing, дрейф `.env.example`, миграции в entrypoint при
нескольких репликах, отсутствие branch protection, отзыв JWT (`KI-027`).
