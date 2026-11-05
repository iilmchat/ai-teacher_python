# TODO_V0.4.md — план разработки v0.4.0 «Production & Multi-node»

> Четвёртый этап. Продолжение [TODO_V0.3.md](TODO_V0.3.md) (v0.3.x «Ops & Scale»).
> Правила — [docs/RULES.md](docs/RULES.md), контракты — [docs/SPEC.md](docs/SPEC.md),
> реестр проблем — [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md),
> журнал спринтов — [docs/RELEASES.md](docs/RELEASES.md).
>
> Статусы задач: `[ ]` — не начата, `[~]` — в работе, `[x]` — выполнена,
> `[!]` — заблокирована (см. `KI-NNN`).

**Целевая версия:** v0.4.0  
**Создан:** 2026-11-02  
**Обновлён:** 2026-11-05 — детализация спринтов 33–41  
**Базис:** v0.3.3 (2026-11-05)  
**Статус:** в работе — спринт 33; S33-001 и S33-002 закрыты  
**Оценка этапа:** ~26 инженерных дней (оценки ±30%, без ожидания доступов)  
**Следующий свободный KI:** `KI-031`  
**Следующий этап:** [TODO_V0.5.md](TODO_V0.5.md) — план v0.5.0 «Learning Experience & Teaching Workflow»

---

## 0. Цель этапа

v0.3.x сделал продукт эксплуатируемым на одном узле. v0.4.0 делает его
**промышленным**: несколько реплик без общих точек отказа, наблюдаемость с
дашбордами и алертами как кодом, воспроизводимые деплой/бэкапы/откаты,
управляемая цепочка поставки и закрытый merge-gate.

### 0.1. Критерии успеха этапа

| Критерий | Проверяемое доказательство |
|----------|-----------------------------|
| Воспроизводимая сборка | все `FROM`/`image:` закреплены по digest; guard в CI; сборка повторяется на другой машине |
| Управляемая supply chain | `hadolint` + `trivy` без HIGH/CRITICAL; SBOM CycloneDX в релизе; Dependabot без долга |
| Наблюдаемость | `/metrics`, OTel-трейсы, дашборды и алерты поднимаются из репозитория; есть SLO |
| Мультиреплика | 2+ backend проходят e2e; метрики суммируются; фоновые задачи не дублируются |
| Восстановление | бэкап по расписанию + off-site; restore drill автоматизирован и зелёный |
| Деплой | rolling restart, health-gate и откат одной командой |
| Гейты | красный PR не мержится (или `KI-023` явно `Blocked` с ручным fallback); coverage-гейт |
| Безопасность | ASVS L1 пройден; секретов в конфигах нет; `KI-027` закрыт или сужен с планом |
| Документация | ADR, runbook, upgrade-гайд, отчёты по шагам и спринтам, `CHANGELOG`, `RELEASES` |
| Релиз | тег `v0.4.0`, GitHub/GitFlic Release, SBOM и checksums, проверенный откат |

### 0.2. Принципы этапа

1. **Сначала измеримость, потом масштаб.** Ни один переход на N реплик не
   начинается без дашбордов, алертов и SLO из спринта 34.
2. **Автоматизация вместо памяти.** Бэкап, откат, миграции, релиз — команды,
   а не чек-лист «помню, как делал».
3. **Каждый gate воспроизводится локально.** Если проверку нельзя запустить
   одной командой, она не гейт, а пожелание.
4. **Один источник правды.** Детали задач живут здесь; `RELEASES.md` хранит
   только статус и итоги, `README.md` — навигацию.

---

## 1. Что не так с инженерной практикой (аудит v0.3.3)

Оценка по чек-листу зрелой production-практики. `✅` — есть, `⚠️` — частично,
`❌` — нет.

| Практика | Статус | Комментарий | Приоритет |
|----------|--------|-------------|-----------|
| Лицензия и юридическая определённость | ✅ (v0.3.3) | `LICENSE` (MIT) добавлен; в `pyproject.toml` — `license` | — |
| Политика безопасности (SECURITY.md) | ✅ (v0.3.3) | контакт, SLA, скоуп, процесс | — |
| Merge-gate (required checks) | ❌ | `KI-023`: GitHub Free не даёт branch protection; нужен GitFlic MR-гейт или Pro | P0 |
| Dependabot-долг | ⚠️ | 15 открытых PR, авто-мержа нет (заблокирован `KI-023`) | P0 |
| Пиннинг образов по digest | ✅ (S33-001) | runtime-образы и compose закреплены; guard `check_image_pins.py` | — |
| Сканирование образов (`trivy`/`hadolint`) | ❌ | план S33-003; CI-образы пока не закреплены | P0 |
| SBOM как артефакт релиза | ❌ | план S33-004 | P1 |
| Non-root в Dockerfile | ✅ (S33-002) | backend — `USER app` (10001); frontend — статика за nginx, master по умолчанию root | — |
| Бэкапы: расписание, off-site, проверка восстановления | ⚠️ | `scripts/backup.sh`/`restore.sh` есть, расписания и off-site нет | P0 |
| Трейсинг и алерты как код | ❌ | структурированные логи есть, OTel нет; алерты только текстом в `DESIGN_ADMIN_AND_OPS` §10 | P1 |
| Дашборды Grafana в репозитории | ❌ | мониторинг описан, конфигов нет | P1 |
| Покрытие тестами как гейт | ⚠️ | `fail_under = 70` в `pyproject.toml`, но CI `pytest -q` без `--cov` | P1 |
| Pre-commit / локальные хуки | ❌ | гейты только в CI и вручную | P1 |
| Zero-downtime деплой и откат | ❌ | `docker compose up -d`, миграции в entrypoint | P1 |
| Управление секретами | ❌ | `SECRET_KEY`/ключи LLM в ENV и compose | P1 |
| PII/DPIA и ASVS | ⚠️ | `PRIVACY.md` есть; DPIA и чек-лист ASVS L1 — нет | P1 |
| Чек-лист совместимости API/депрекаций | ⚠️ | `/api/v1`, контрактные тесты, но политики депрекации нет | P2 |
| SLO/бюджеты ошибок | ❌ | есть нефункциональные требования, SLO не сформулированы | P2 |
| Feature flags | ❌ | флаги ENV есть, механизма включения на пользователя нет | P2 |
| Мультиреплика: WS, метрики, планировщики | ⚠️ | метрики (`MULTIPROCESS`), retention (advisory lock) готовы; WS и балансировка — нет | P1 |

**Не является проблемой (сделано и подтверждено):** структурированные логи и
request-id, `/health/live|ready`, retention, экспорт ПДн, a11y/i18n-аудит,
контрактные тесты OpenAPI, e2e Playwright, gitleaks, pip-audit/pnpm audit,
perf-smoke, миграционные тесты, `alembic check`.

---

## 2. Спринт 32 (v0.3.2) + патч v0.3.3 — закрыто

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

**Перенесено в v0.4.0:** расписание/off-site бэкапов (S36), digest-пиннинг
CI-образов и сканирование (S33), non-root backend (S33-002, закрыто),
coverage-гейт (S37).

---

## 3. Карта KI → спринты

| KI | Severity | Статус | Спринт | Действие |
|----|----------|--------|--------|----------|
| `KI-023` | High | Open | 37 (старт — сразу) | Владелец: GitFlic-агент/токен или GitHub Pro; включить required checks и проверить красным MR. Fallback — ручной гейт по RULES §10 |
| `KI-027` | Accepted · Low | Accepted | 38 | `token_version` + отзыв refresh/logout; перенос токенов в httpOnly-cookie/BFF — v0.5, зафиксировать в KI |
| `KI-018` | Accepted · Low | Accepted | — | Не менять: `.format()` запрещён RestrictedPython; пересмотреть при обновлении библиотеки |
| `KI-017` | Low | Resolved | 33, 37 | Не KI-действие, а риск окружения: PyPI/trivy DB/зеркала; wheelhouse и кэш |

Новые проблемы заводим сразу с `KI-NNN` (следующий свободный — **KI-031**;
`KI-028`…`KI-030` заняты планом v0.5.0 — см. [TODO_V0.5.md](TODO_V0.5.md) §3).
Кандидаты: отсутствие tracing (S34), дрейф `.env.example` (S40), миграции в
entrypoint при нескольких репликах (S36), отсутствие branch protection
(`KI-023`), отзыв JWT (`KI-027`), лимиты мониторинга на одном узле (S34).

---

## 4. Обзор спринтов

| Спринт | Тема | Зависит от | Оценка | Статус | Ключевой результат |
|--------|------|------------|--------|--------|--------------------|
| 33 | Supply chain & Repo hygiene | v0.3.3 | 3 дня | `[~]` | digest везде, сканы, SBOM, hooks, единые команды |
| 34 | Observability 2.0 | 33 | 3 дня | `[ ]` | OTel, Prometheus, Grafana, SLO, алерты как код |
| 35 | Multi-node readiness | 34 | 3 дня | `[ ]` | 2+ реплики, WS, агрегированные метрики, locks |
| 36 | Deploy, Backup & DR | 35 | 3,5 дня | `[ ]` | rolling deploy, откат, off-site, restore drill |
| 37 | CI Gates & GitFlic | 33; `KI-023` | 3 дня | `[ ]` | required checks, паритет CI, coverage-гейт |
| 38 | Security & Privacy | 33, 34 | 3,5 дня | `[ ]` | DPIA, секреты, `KI-027`, ASVS L1 |
| 39 | Performance & Capacity | 34, 35 | 2,5 дня | `[ ]` | nightly-нагрузка, N+1, кэш, ёмкость |
| 40 | DX & Docs | 33–39 | 2 дня | `[ ]` | ADR, онбординг, CONTRIBUTING, env-drift |
| 41 | Release v0.4.0 | 33–40 | 2,5 дня | `[ ]` | upgrade, тег, релизы, проверенный откат |

**Порядок и логика:**

- 33 первый: reproducible-образы и сканы — фундамент для всех остальных.
- 34 до 35: сначала измеряем, потом масштабируем.
- 35 до 36: деплой/DR проектируются уже под несколько реплик.
- 37 можно вести параллельно после 33; действие владельца по `KI-023` —
  длинный lead time, начинать сразу.
- 38, 39, 40 — параллельные ветки после 34/35; при одном разработчике это
  последовательное переключение, а не одновременная работа.
- 41 последний: собирает результаты всех спринтов.

---

## 5. План по спринтам

### Спринт 33: Supply chain & Repo hygiene — `[~]`

**Цель:** воспроизводимые образы, управляемые зависимости и локальные хуки,
совпадающие с CI.

**Зависит от:** v0.3.3  
**Оценка:** 3 дня (остаток ~2,5 дня)  
**Закрывает/снижает:** долг Dependabot, риск `KI-017`; готовит `KI-023`  
**Отчёт:** `docs/reports/sprint-33/SPRINT-33.md`

#### S33-001: Digest-пиннинг runtime-образов — `[x]`

- [x] `python:3.12-slim`, `node:22-alpine`, `nginx:1.27-alpine`,
      `pgvector/pgvector:pg17`, `redis:7-alpine` закреплены по digest в
      Dockerfile'ах и compose.
- [x] Guard `backend/scripts/check_image_pins.py` + 7 тестов; вызов в
      `scripts/ci/backend-lint.sh`.
- [x] Отчёт: `docs/reports/sprint-33/STEP-01_IMAGE_PINS_NONROOT.md`.
- [x] **Зависит от:** — · **Оценка:** 8 ч (выполнено)

#### S33-002: Non-root backend — `[x]`

- [x] `USER app` (UID/GID 10001), `/app` read-only, запись только в `/tmp`
      и `PROMETHEUS_MULTIPROC_DIR`; `PYTHONDONTWRITEBYTECODE=1`.
- [x] Проверены `id`, запись в `/tmp`, `[ -w /app ]` → false, `alembic check`,
      `/health/ready`, полный `pytest` в образе.
- [x] **Зависит от:** S33-001 · **Оценка:** 8 ч (выполнено)

#### S33-003: CI-образы, `hadolint` и `trivy` — `[ ]`

- [ ] Закрепить по digest все образы в CI: `python:3.12-slim`,
      `node:22-alpine`, `pgvector/pgvector:pg17`, `redis:7-alpine`, `gitleaks`
      в `.github/workflows/ci.yml`, `ci-selfhosted.yml`, `release.yml`,
      `gitflic-ci.yaml`, `ci/gitflic-pilot.yaml`,
      `scripts/ci/build-wheelhouse.ps1`; убрать дубли пилота.
- [ ] Решить и зафиксировать политику для GitHub Actions: полный commit SHA
      (предпочтительно) или major-тег + Dependabot; обоснование — в
      `docs/CI.md`.
- [ ] Расширить `backend/scripts/check_image_pins.py` на workflow/CI-YAML и
      скрипты; добавить тесты на новые файлы; guard остаётся в lint.
- [ ] `.hadolint.yaml` (игноры только с обоснованием) и `trivy image
      --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1` для backend,
      frontend и sandbox-runner; отчёты — артефактами.
- [ ] `scripts/ci/supply-chain.ps1` + `.sh`, job в GitHub и GitFlic;
      локальная команда `make supply-chain`.
- [ ] **Зависит от:** S33-001 · **Оценка:** 6 ч

#### S33-004: SBOM CycloneDX — `[ ]`

- [ ] Генерировать CycloneDX SBOM для трёх образов через `trivy`
      (`artifacts/sbom/*.cdx.json`) + `SHA256SUMS`.
- [ ] Прикреплять SBOM к GitHub Release и GitFlic Release; хранить артефакты
      не менее 90 дней.
- [ ] Лёгкая проверка `scripts/ci/verify_sbom.py`: непустой список
      компонентов, совпадение base-digest, отсутствие дублей.
- [ ] **Зависит от:** S33-003 · **Оценка:** 3 ч

#### S33-005: Dependabot — политика, долг и repo hygiene — `[ ]`

- [ ] Инвентаризировать 15 открытых PR: смержить зелёные minor/patch,
      закрыть устаревшие с комментарием, major — отдельно с причиной;
      таблица решений — в отчёте спринта.
- [ ] Обновить `.github/dependabot.yml`: добавить `docker`-экосистему,
      группы для actions, лимиты, cooldown (если поддерживается); политика
      major — только вручную.
- [ ] Авто-мерж остаётся заблокированным `KI-023`; зафиксировать ручной SLA
      (триаж раз в неделю, мерж только после зелёного CI) в `docs/CI.md` §13.
- [ ] Repo hygiene: удалить смерженные ветки, проверить теги, `.gitignore`,
      `.gitattributes`, отсутствие крупных/секретных файлов.
- [ ] **Зависит от:** S33-003 · **Оценка:** 3 ч

#### S33-006: Pre-commit — `[ ]`

- [ ] `.pre-commit-config.yaml`: trailing-whitespace, end-of-file-fixer,
      check-yaml, check-merge-conflict, check-added-large-files; `ruff`;
      `gitleaks`; локальные хуки `check-i18n.mjs`, `check_version.py`,
      `check_image_pins.py`.
- [ ] `pre-commit run --all-files` зелёный; тот же набор запускается в CI,
      чтобы локальные и CI-гейты не расходились.
- [ ] Инструкция для Windows/macOS/Linux — `CONTRIBUTING.md` (создаётся в S40),
      краткая версия — `docs/GETTING_STARTED.md` и `RULES.md`.
- [ ] **Зависит от:** S33-003, S33-005 · **Оценка:** 3 ч

#### S33-007: Единые команды (`Makefile` + PowerShell) — `[ ]`

- [ ] `Makefile`: `help`, `lint`, `test`, `test-fast`, `test-image`, `e2e`,
      `frontend`, `docker`, `supply-chain`, `release-check`; команды делегируют
      в `scripts/ci/*`, без дублирования логики.
- [ ] `scripts/tasks.ps1` с теми же целями для Windows (PowerShell 7);
      `Makefile` — тонкая обёртка для Git Bash/Linux/CI.
- [ ] `make release-check` = все гейты без создания релиза; `make test-image` =
      полный `pytest` в собранном образе.
- [ ] Таблица команд в `docs/GETTING_STARTED.md`; ссылка из `docs/README.md`.
- [ ] **Зависит от:** S33-003 · **Оценка:** 4 ч

#### S33-008: Документация и закрытие спринта — `[ ]`

- [ ] `RULES.md` §11.27: CI-образы, `trivy`/`hadolint`, SBOM, pre-commit.
- [ ] `docs/CI.md`: новые job'ы, артефакты, политика Actions/Dependabot.
- [ ] `CHANGELOG.md` (`[Unreleased]`), `RELEASES.md`, отчёт `SPRINT-33.md`.
- [ ] **Зависит от:** S33-003…S33-007 · **Оценка:** 2 ч

**DoD:** все `FROM`/`image:` и CI-образы закреплены; guard покрывает новые
файлы; `hadolint`/`trivy` — 0 HIGH/CRITICAL (или принято с expiry); SBOM
генерируется; `pre-commit run --all-files` и `make lint/test` зелёные;
Dependabot-долг разобран; спринт-отчёт заполнен.

---

### Спринт 34: Observability 2.0 — `[ ]`

**Цель:** по метрикам, трейсам и логам можно ответить «что сломалось и где»;
дашборды, алерты и SLO лежат в репозитории и поднимаются одной командой.

**Зависит от:** спринт 33  
**Оценка:** 3 дня  
**Закрывает:** кандидат KI «нет tracing» (завести при необходимости)  
**Отчёт:** `docs/reports/sprint-34/SPRINT-34.md`

#### S34-001: OpenTelemetry-трейсы — `[ ]`

- [ ] Зависимости OTel + `app/core/tracing.py`: FastAPI, SQLAlchemy, httpx,
      Redis; OTLP HTTP exporter; `OTEL_ENABLED=false` по умолчанию,
      `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`, sampler.
- [ ] Спаны `llm.request` (provider/model/status/tokens, **без** prompt и
      completion), `sandbox.run`, `job.run`; `traceparent` пробрасывается.
- [ ] Тесты с in-memory exporter и тест no-op при выключенном флаге; PII в
      атрибутах не пишется.
- [ ] **Зависит от:** — · **Оценка:** 5 ч

#### S34-002: Prometheus и алерты как код — `[ ]`

- [ ] `deploy/monitoring/prometheus/prometheus.yml`, `rules/alerts.yml`,
      `rules/recording.yml`; `promtool check config` и `check rules` в CI.
- [ ] Алерты: 5xx rate, p95 API, LLM error rate, sandbox timeouts,
      retention failures, DB pool saturation, target down, backup stale,
      disk low; `severity`, `runbook_url`, `summary`.
- [ ] Если для алерта нет метрики — добавить её (например,
      `backup_last_success_timestamp`, `scheduler_last_success_timestamp`).
- [ ] **Зависит от:** S34-001 · **Оценка:** 4 ч

#### S34-003: Grafana-дашборды как код — `[ ]`

- [ ] `deploy/monitoring/grafana/provisioning/{datasources,dashboards}`;
      JSON-дашборды: API overview, LLM/FinOps, sandbox, DB/Redis, ops/backups.
- [ ] Переменные `instance`, `route`, `provider`; единицы измерения и пороги
      соответствуют SLO.
- [ ] Smoke: Grafana поднимается с provisioning, панели получают данные;
      скриншот/краткое описание — в `docs/MONITORING.md`.
- [ ] **Зависит от:** S34-002 · **Оценка:** 5 ч

#### S34-004: Логи, ротация и стек мониторинга — `[ ]`

- [ ] Docker logging: `json-file` с `max-size`/`max-file` для всех сервисов;
      опциональный профиль `monitoring` с Loki/Promtail.
- [ ] `docker-compose.monitoring.yml` (или profile в prod compose) с лимитами
      ресурсов; `make monitoring-up/down`; без мониторинга прод работает.
- [ ] Примеры LogQL-запросов, политика отсутствия PII в логах; ссылка из
      `RULES.md`.
- [ ] **Зависит от:** S34-002 · **Оценка:** 3 ч

#### S34-005: SLO и бюджеты ошибок — `[ ]`

- [ ] `docs/SLO.md`: SLI/SLO (доступность 99,5%/30 дней, p95 API ≤ 500 мс,
      submit p95 ≤ 2 с, успешные LLM-ответы ≥ 99%), error budget, burn-rate
      алерты, владелец.
- [ ] Связь «алерт → SLO → runbook»; ссылки из `DESIGN_ADMIN_AND_OPS` §10 и
      `docs/MONITORING.md` (без дублирования таблиц).
- [ ] **Зависит от:** S34-002 · **Оценка:** 3 ч

#### S34-006: Документация и закрытие спринта — `[ ]`

- [ ] `docs/MONITORING.md`: архитектура, команды, каталог алертов,
      troubleshooting, ограничения одного узла.
- [ ] `CHANGELOG.md`, `RELEASES.md`, отчёт `SPRINT-34.md`.
- [ ] **Зависит от:** S34-001…S34-005 · **Оценка:** 2 ч

**DoD:** `docker compose --profile monitoring up -d` поднимает Prometheus,
Grafana и (опционально) Loki; все targets `UP`; правила и дашборды
валидируются; SLO-документ есть; OTel можно включить флагом; PII в трейсах и
логах не появляется.

---

### Спринт 35: Multi-node readiness — `[ ]`

**Цель:** 2+ реплики backend работают без общих точек отказа; метрики
суммируются, фоновые задачи не дублируются, WebSocket не рвётся.

**Зависит от:** спринт 34  
**Оценка:** 3 дня  
**Отчёт:** `docs/reports/sprint-35/SPRINT-35.md`

#### S35-001: WebSocket и балансировка — `[ ]`

- [ ] Решение зафиксировать в `ARCHITECTURE.md`: sticky sessions на nginx
      (`ip_hash` или cookie `route`) для `/api/v1/chat/ws/`; Redis pub/sub —
      только если нужен broadcast (не для стрима одного чата).
- [ ] nginx upstream: `resolver 127.0.0.11`, `least_conn` для HTTP, sticky для
      WS, `proxy_next_upstream`, health checks; проверка 2 реплик.
- [ ] e2e: подключение, стриминг, переподключение при падении одной реплики.
- [ ] **Зависит от:** — · **Оценка:** 6 ч

#### S35-002: Воркеры и multiprocess-метрики — `[ ]`

- [ ] `UVICORN_WORKERS` (prod default 2–4), `PROMETHEUS_MULTIPROC_DIR` в prod
      compose; каталог чистится entrypoint'ом, у каждой реплики свой.
- [ ] Интеграционный тест: 4 воркера, запросы, scrape `/metrics`; счётчики
      суммируются, гистограммы агрегируются, семантика gauge описана.
- [ ] Prometheus scrape для 2+ targets/реплик, `instance` в метриках.
- [ ] **Зависит от:** S34-002 · **Оценка:** 4 ч

#### S35-003: Общее состояние: rate limit, кэш, сессии — `[ ]`

- [ ] Аудит на process-local состояние: rate limiter, кэш, LLM semaphore,
      сессии; всё общее — Redis/PostgreSQL, ключи с namespace и TTL.
- [ ] Тест двух инстансов с общим Redis: лимит 5/мин суммарный, инвалидация
      кэша видна обоим, данные пользователей не пересекаются.
- [ ] **Зависит от:** S35-002 · **Оценка:** 4 ч

#### S35-004: Фоновые задачи без дублей — `[ ]`

- [ ] Инвентаризация: retention scheduler, `notify_deadlines.py`, будущие
      периодические задачи; единый `app/core/locks.py` (advisory lock или
      Redis lock с owner/TTL).
- [ ] Тест concurrent-запуска на 2 репликах: выполняет ровно один, лок
      освобождается при падении; метрика `job_runs_total{job,status}`.
- [ ] **Зависит от:** S35-002 · **Оценка:** 4 ч

#### S35-005: Graceful shutdown и rolling restart — `[ ]`

- [ ] `stop_grace_period`, `--timeout-graceful-shutdown`, `proxy_next_upstream`,
      порядок `start-first`; корректное закрытие WS и пула БД.
- [ ] Healthcheck не пропускает трафик в ещё не готовую реплику; проверка
      rolling restart без 5xx на e2e/smoke.
- [ ] **Зависит от:** S35-001 · **Оценка:** 3 ч

#### S35-006: E2E на 2 репликах и документация — `[ ]`

- [ ] `docker compose up --scale backend=2` + e2e/smoke; зафиксировать p95,
      error rate, отсутствие дублей задач.
- [ ] `ARCHITECTURE.md`, `SPEC.md` (multi-node), `RULES.md`,
      `GETTING_STARTED.md`; отчёт `SPRINT-35.md`.
- [ ] **Зависит от:** S35-001…S35-005 · **Оценка:** 3 ч

**DoD:** 2 реплики проходят e2e и smoke без деградации; WS переживает падение
реплики; метрики суммируются; фоновые задачи не дублируются; rolling restart
не даёт 5xx; ограничения compose-мультиреплики описаны.

---

### Спринт 36: Deploy, Backup & DR — `[ ]`

**Цель:** деплой, откат, бэкап и восстановление — воспроизводимые команды,
а не чек-лист «помню, как делал».

**Зависит от:** спринт 35  
**Оценка:** 3,5 дня  
**Отчёт:** `docs/reports/sprint-36/SPRINT-36.md`

#### S36-001: Миграции отдельным job'ом — `[ ]`

- [ ] One-shot `migrate` (compose service/`run --rm`), приложение стартует с
      `SKIP_MIGRATIONS=true`; порядок «migrate → health → app».
- [ ] Ошибка миграции останавливает rollout; таймаут и лог; тест на пустой БД
      и на уже применённой.
- [ ] **Зависит от:** — · **Оценка:** 4 ч

#### S36-002: `deploy` и `rollback` — `[ ]`

- [ ] `scripts/deploy.ps1` + `deploy.sh`: preflight (`compose config`, ENV,
      диск), бэкап, сборка/пул версионированных образов (`:<git-sha>`),
      миграции, rolling restart, health-gate `/health/ready`, smoke.
- [ ] При ошибке — автоматический откат на предыдущий тег; состояние в
      `.deploy-state` (gitignored); `--dry-run`, `--no-backup`, `--version`;
      коды выхода.
- [ ] **Зависит от:** S36-001 · **Оценка:** 8 ч

#### S36-003: Бэкапы: расписание и off-site — `[ ]`

- [ ] Расширить `scripts/backup.sh`: `--upload` (rclone/S3-совместимое),
      опциональное шифрование (`age`/`gpg`), manifest, checksum, `--dry-run`.
- [ ] systemd timer/cron + Windows Task Scheduler; `BACKUP_*` ENV; метрика
      `backup_last_success_timestamp` для алерта `BackupStale`.
- [ ] **Зависит от:** S34-002 · **Оценка:** 6 ч

#### S36-004: Автоматический restore drill — `[ ]`

- [ ] `scripts/restore-drill.sh|ps1`: последний бэкап → scratch-БД →
      `pg_restore` → `alembic current` → проверки counts/health → удаление
      scratch; `--keep`, `--verify`, `--dry-run`.
- [ ] Ночной/недельный запуск и артефакт-отчёт; проверка, что drill не трогает
      рабочую БД.
- [ ] **Зависит от:** S36-003 · **Оценка:** 4 ч

#### S36-005: Runbook инцидентов — `[ ]`

- [ ] `docs/RUNBOOK.md`: БД недоступна, Redis, LLM, песочница, диск, TLS,
      бэкап/restore, откат; симптомы → проверки → действия → эскалация.
- [ ] Ссылки на дашборды/алерты/скрипты; обновить `DESIGN_ADMIN_AND_OPS` §10.
- [ ] **Зависит от:** S34-002, S36-002…S36-004 · **Оценка:** 4 ч

#### S36-006: Документация и закрытие спринта — `[ ]`

- [ ] `UPGRADE.md`, `GETTING_STARTED.md`, `RULES.md`; `CHANGELOG.md`,
      `RELEASES.md`, отчёт `SPRINT-36.md`.
- [ ] **Зависит от:** S36-001…S36-005 · **Оценка:** 2 ч

**DoD:** откат на предыдущую версию — одна команда, проверенная на стенде;
restore drill зелёный; бэкап уходит off-site; runbook покрывает ключевые
инциденты; алерт `BackupStale` связан с реальной метрикой.

---

### Спринт 37: CI Gates & GitFlic — `[ ]`

**Цель:** красный PR физически не мержится; все гейты воспроизводимы локально
и не зависят от памяти ревьюера.

**Зависит от:** спринт 33; действие владельца по `KI-023`  
**Оценка:** 3 дня (часть может быть `Blocked`)  
**Закрывает:** `KI-023` — при наличии доступа владельца  
**Отчёт:** `docs/reports/sprint-37/SPRINT-37.md`

#### S37-001: GitFlic-агент и required checks (`KI-023`) — `[ ]`

- [ ] Владелец: зарегистрировать PowerShell/Docker-агент, выдать токен,
      включить MR-пайплайн и «проверять статус последнего конвейера».
- [ ] Проверить на тестовом MR, что красный конвейер блокирует merge; если
      нет — gate через webhook/скрипт, решение — в `docs/CI.md`.
- [ ] Если доступа нет к началу спринта: `KI-023` остаётся `Blocked`,
      фиксируем fallback (ручной гейт + `gates.ps1|sh`), не имитируем гейт.
- [ ] **Зависит от:** доступ владельца · **Оценка:** 6 ч + ожидание

#### S37-002: Паритет GitHub ↔ GitFlic — `[ ]`

- [ ] Сопоставить job'ы (lint, test, frontend, security, e2e, docker, perf) с
      этапами GitFlic; одинаковые команды, образы, кэш, артефакты.
- [ ] `gitflic-ci.yaml` — digest-пиннинг, path-фильтры, `needs`, таймауты;
      убрать расхождения и мёртвые job'ы.
- [ ] **Зависит от:** S33-003 · **Оценка:** 5 ч

#### S37-003: Coverage-гейт — `[ ]`

- [ ] Backend: `pytest --cov=app --cov-report=xml --cov-fail-under=70` в CI;
      отчёт — артефакт, порог не снижать без записи в KI.
- [ ] Frontend: thresholds в конфиге Vitest (lines/functions/branches/
      statements), отчёт в CI; текущий замер 73,6% строк.
- [ ] **Зависит от:** S37-002 · **Оценка:** 3 ч

#### S37-004: Скорость и надёжность CI — `[ ]`

- [ ] `timeout-minutes`, `concurrency: cancel-in-progress`, кэш pip/pnpm,
      Docker layer cache, разумный retention артефактов.
- [ ] Цель: lint+test+frontend < 15 мин; измерить до/после, записать в
      `docs/CI.md`.
- [ ] **Зависит от:** S37-002 · **Оценка:** 3 ч

#### S37-005: Единый локальный прогон гейтов — `[ ]`

- [ ] `scripts/ci/gates.ps1` + `gates.sh`: `--fast` (lint/type/unit),
      `--full` (+ e2e, docker, supply-chain, coverage), `--ci` (без интерактива),
      JSON-сводка; коды выхода.
- [ ] `make release-check` вызывает тот же скрипт; список гейтов совпадает с
      CI (проверка тестом/скриптом).
- [ ] **Зависит от:** S37-002 · **Оценка:** 4 ч

#### S37-006: Документация и закрытие спринта — `[ ]`

- [ ] `RULES.md` §10, `docs/CI.md`, `KNOWN_ISSUES.md` (`KI-023`),
      `CHANGELOG.md`, `RELEASES.md`, отчёт `SPRINT-37.md`.
- [ ] **Зависит от:** S37-001…S37-005 · **Оценка:** 2 ч

**DoD:** красный MR не мержится (проверено тестовым MR) или `KI-023` явно
`Blocked` с работающим ручным fallback; coverage-гейт активен; локальный
`gates --full` совпадает с CI; CI укладывается в целевое время.

---

### Спринт 38: Security & Privacy — `[ ]`

**Цель:** закрыть security/privacy-долг, подтвердить ASVS L1 и убрать секреты
из конфигов.

**Зависит от:** спринты 33, 34  
**Оценка:** 3,5 дня  
**Закрывает:** `KI-027` (частично: `token_version`/logout; cookie/BFF — v0.5)  
**Отчёт:** `docs/reports/sprint-38/SPRINT-38.md`

#### S38-001: Инвентаризация PII и DPIA — `[ ]`

- [ ] Инвентаризация: email, имя, чаты, код, эмбеддинги, audit IP; где
      хранится, срок, кто обработчик (DeepSeek/LLM), трансграничная передача.
- [ ] `docs/PRIVACY.md` (приложение) или `docs/DPIA.md`: цели, правовое
      основание, права субъекта, меры защиты, остаточные риски.
- [ ] **Зависит от:** — · **Оценка:** 4 ч

#### S38-002: Секреты вне конфигов — `[ ]`

- [ ] Поддержка Docker secrets / `*_FILE` для `SECRET_KEY`,
      `DEEPSEEK_API_KEY`, `POSTGRES_PASSWORD`, SMTP; приоритет file над ENV.
- [ ] `docker-compose.prod.yml`: secrets вместо открытых значений; примеры и
      процедура ротации; стартовая валидация небезопасных значений.
- [ ] Тесты на `_FILE` и приоритет; `gitleaks` остаётся гейтом.
- [ ] **Зависит от:** S33-006 · **Оценка:** 6 ч

#### S38-003: Отзыв JWT (`KI-027`) — `[ ]`

- [ ] Миграция `users.token_version` (следующая свободная, ожидается 014);
      claim `ver` в access/refresh; проверка в `get_current_user` и refresh.
- [ ] Инкремент при смене пароля/роли/деактивации/удалении; `POST /auth/logout`
      отзывает refresh (denylist `jti` до exp или `token_version`).
- [ ] Тесты: старый access/refresh отклоняются после смены пароля/логаута;
      неактивный пользователь — отклонён.
- [ ] Хранение токенов в httpOnly-cookie/BFF **не входит** в v0.4.0:
      зафиксировать в `KI-027` как следующий шаг (v0.5), не терять риск XSS.
- [ ] **Зависит от:** S38-001 · **Оценка:** 8 ч

#### S38-004: Заголовки, CSP и TLS — `[ ]`

- [ ] Проверить CSP/security headers после добавления мониторинга и WS;
      добавить `Cross-Origin-Opener-Policy`/`Cross-Origin-Resource-Policy`,
      если не ломают Monaco и API.
- [ ] HSTS — только при реальном TLS; пример терминации (nginx/certbot или
      внешний proxy), проверка `curl -I`.
- [ ] **Зависит от:** S34 · **Оценка:** 3 ч

#### S38-005: OWASP ASVS L1 — `[ ]`

- [ ] `docs/ASVS_L1.md`: чек-лист с доказательствами (auth, session, access
      control, validation, crypto, errors/logging, data protection,
      configuration); автоматические тесты где возможно.
- [ ] Открытые пункты — в `KNOWN_ISSUES.md` с severity и планом; без
      «галочек» без доказательств.
- [ ] **Зависит от:** S38-002…S38-004 · **Оценка:** 5 ч

#### S38-006: Документация и закрытие спринта — `[ ]`

- [ ] `SECURITY.md`, `PRIVACY.md`, `RULES.md`, `KNOWN_ISSUES.md` (`KI-027`),
      `CHANGELOG.md`, `RELEASES.md`, отчёт `SPRINT-38.md`.
- [ ] **Зависит от:** S38-001…S38-005 · **Оценка:** 2 ч

**DoD:** ASVS L1 пройден без открытых High; секретов в конфигах нет; `KI-027`
закрыт или явно сужен с планом на v0.5; заголовки/TLS проверены; DPIA и
инвентаризация PII готовы.

---

### Спринт 39: Performance & Capacity — `[ ]`

**Цель:** известна ёмкость узла, а регресс производительности ловится nightly,
а не пользователями.

**Зависит от:** спринты 34, 35  
**Оценка:** 2,5 дня  
**Отчёт:** `docs/reports/sprint-39/SPRINT-39.md`

#### S39-001: Нагрузочный тест в nightly — `[ ]`

- [ ] Расширить `scripts/load_test.py`: submit, chat/stream, list/detail,
      смешанный сценарий; пороги p95/RPS/error rate; baseline в
      `docs/reports/perf/baseline.json`.
- [ ] Nightly workflow (GitHub + GitFlic), падение при регрессе > 20%;
      отчёт-артефакт с сырыми цифрами.
- [ ] **Зависит от:** S35-006 · **Оценка:** 6 ч

#### S39-002: N+1 и индексы — `[ ]`

- [ ] `pg_stat_statements` в dev/compose, сбор топ-запросов; SQLAlchemy echo в
      тестах; query-count проверки для ключевых эндпоинтов.
- [ ] `EXPLAIN` для медленных запросов; недостающие индексы — миграцией
      (следующая свободная, ожидается 015); без индексов «на всякий случай».
- [ ] **Зависит от:** S35-003 · **Оценка:** 6 ч

#### S39-003: Кэш: hit-rate и инвалидация — `[ ]`

- [ ] Цель hit-rate (например, ≥ 70% для справочных данных); метрики
      `cache_hits_total`/`cache_misses_total`, панель и алерт.
- [ ] Инвалидация по тегам/версиям ключей, защита от stampede; тесты на
      консистентность между репликами.
- [ ] **Зависит от:** S35-003 · **Оценка:** 3 ч

#### S39-004: Ёмкость и прогноз — `[ ]`

- [ ] `docs/CAPACITY.md`: RPS на узел, p95, соединения БД, память/CPU, рост
      диска, прогноз с учётом retention; замер на 1 и 2 репликах.
- [ ] Рекомендации: workers, pool size, лимиты контейнеров, пороги
      масштабирования; ссылки на дашборды.
- [ ] **Зависит от:** S39-001 · **Оценка:** 3 ч

#### S39-005: Документация и закрытие спринта — `[ ]`

- [ ] `DESIGN_ADMIN_AND_OPS`, `RULES.md`, `CHANGELOG.md`, `RELEASES.md`,
      отчёт `SPRINT-39.md`.
- [ ] **Зависит от:** S39-001…S39-004 · **Оценка:** 2 ч

**DoD:** nightly-нагрузка зелёная с порогами и baseline; N+1 на ключевых
эндпоинтах отсутствует; hit-rate кэша измеряется; ёмкость узла описана
цифрами; регресс ловится автоматически.

---

### Спринт 40: DX & Docs — `[ ]`

**Цель:** новый разработчик поднимает проект по документации без вопросов, а
архитектурные решения зафиксированы в ADR.

**Зависит от:** спринты 33–39 (по мере готовности)  
**Оценка:** 2 дня  
**Отчёт:** `docs/reports/sprint-40/SPRINT-40.md`

#### S40-001: ADR — `[ ]`

- [ ] `docs/adr/README.md` + шаблон (Context / Decision / Consequences).
- [ ] Первые ADR: CI-платформа, изоляция песочницы, метрики/наблюдаемость,
      PostgreSQL+pgvector, лицензия MIT, multi-node WS/sticky, секреты.
- [ ] **Зависит от:** S35, S37, S38 · **Оценка:** 4 ч

#### S40-002: Онбординг с нуля — `[ ]`

- [ ] Пройти `GETTING_STARTED.md` на чистой машине/WSL без кэша образов и
      venv; замерить время; починить пробелы.
- [ ] `make bootstrap` / `scripts/bootstrap` (опционально), чек-лист
      «первый запуск», ссылки на troubleshooting.
- [ ] **Зависит от:** S33-007 · **Оценка:** 5 ч

#### S40-003: CONTRIBUTING, CODEOWNERS, шаблоны — `[ ]`

- [ ] `CONTRIBUTING.md`: ветки, коммиты, гейты, отчёты, ревью, релиз.
- [ ] `.github/CODEOWNERS`, issue-шаблоны (bug/feature), PR-шаблон со
      ссылками на `gates` и отчёт.
- [ ] **Зависит от:** S37-005 · **Оценка:** 3 ч

#### S40-004: Дрейф `.env.example` ↔ `Settings` — `[ ]`

- [ ] Тест: парсит `Settings.model_fields` и `.env.example`, проверяет
      наличие/отсутствие ключей; allowlist для compose-only переменных.
- [ ] Обновить `.env.example`; тест в CI; документировать в `RULES.md`.
- [ ] **Зависит от:** S33-003 · **Оценка:** 3 ч

#### S40-005: Документация и закрытие спринта — `[ ]`

- [ ] `README.md`, `docs/README.md`, `RULES.md`, `CHANGELOG.md`,
      `RELEASES.md`, отчёт `SPRINT-40.md`.
- [ ] **Зависит от:** S40-001…S40-004 · **Оценка:** 2 ч

**DoD:** чистая машина проходит онбординг по docs; ADR и шаблоны готовы;
env-drift ловится тестом; навигация по документации не содержит мёртвых
ссылок.

---

### Спринт 41: Release v0.4.0 — `[ ]`

**Цель:** воспроизводимый релиз v0.4.0 с проверенным обновлением и откатом.

**Зависит от:** спринты 33–40  
**Оценка:** 2,5 дня  
**Отчёт:** `docs/reports/sprint-41/SPRINT-41.md` + итог этапа  
**Отчёт этапа:** `docs/reports/v0.4.0/STAGE.md`

#### S41-001: Руководство по апгрейду 0.3.x → 0.4.0 — `[ ]`

- [ ] `docs/UPGRADE.md`: миграции (ожидаются 014/015), новые ENV (OTel,
      workers, secrets, backup), изменения compose (образы, monitoring,
      multi-node), порядок деплоя, откат, restore.
- [ ] Проверить апгрейд на копии БД v0.3.3; зафиксировать время и проблемы.
- [ ] **Зависит от:** все спринты · **Оценка:** 5 ч

#### S41-002: Версия, CHANGELOG, документация — `[ ]`

- [ ] Версия `0.4.0` в `pyproject.toml`, `frontend/package.json`,
      `backend/app/config.py`; `check_version` — 0 расхождений.
- [ ] `CHANGELOG.md` `[0.4.0]`, `RELEASES.md` (итог этапа), README/бейджи,
      ссылки на новые документы.
- [ ] **Зависит от:** S41-001 · **Оценка:** 3 ч

#### S41-003: Репетиция релиза — `[ ]`

- [ ] Полные гейты; сборка версионированных образов; SBOM + checksums;
      деплой на staging; smoke; откат; restore drill; замеры.
- [ ] Записать найденные проблемы; блокирующие — исправить до тега.
- [ ] **Зависит от:** S41-002 · **Оценка:** 6 ч

#### S41-004: Тег и релизы — `[ ]`

- [ ] Тег `v0.4.0`; GitHub Release + GitFlic Release; артефакты (SBOM,
      checksums, заметки); релизный workflow.
- [ ] Post-release: `/health/ready`, `version=0.4.0`, smoke, проверка
      документации и отката.
- [ ] **Зависит от:** S41-003 · **Оценка:** 3 ч

#### S41-005: Итоговый отчёт этапа — `[ ]`

- [ ] `docs/reports/sprint-41/SPRINT-41.md` и `docs/reports/v0.4.0/STAGE.md`:
      что вошло, метрики, KI, отклонения, уроки.
- [ ] Обновить `TODO_V0.4.md` (все статусы), `KNOWN_ISSUES.md`,
      `RELEASES.md`, `CHANGELOG.md`.
- [ ] **Зависит от:** S41-004 · **Оценка:** 2 ч

**DoD:** тег и оба релиза созданы; SBOM/checksums прикреплены; апгрейд с
v0.3.3 проверен; откат и restore drill проверены; все гейты зелёные; итоговый
отчёт заполнен.

---

## 6. Сквозной DoD этапа

Этап v0.4.0 считается завершённым, когда:

1. **Код и тесты:** `ruff check` — 0, `mypy app` — 0, полный `pytest` в
   собранном образе — зелёный; frontend `typecheck/lint/test/build` — зелёные;
   e2e — зелёные; `alembic check` — чистый.
2. **Supply chain:** все `FROM`/`image:` и CI-образы закреплены; `hadolint` и
   `trivy` — 0 HIGH/CRITICAL (или принято с expiry и записью в KI); SBOM
   CycloneDX прикреплён к релизу; Dependabot-долг разобран.
3. **Наблюдаемость:** метрики, OTel-трейсы (флаг), дашборды, алерты и SLO —
   в репозитории; `docker compose --profile monitoring up -d` работает.
4. **Мультиреплика:** 2+ backend проходят e2e; метрики суммируются; фоновые
   задачи не дублируются; WS переживает падение реплики.
5. **Деплой/DR:** rolling deploy, health-gate, откат одной командой; бэкап по
   расписанию и off-site; restore drill автоматизирован.
6. **Гейты:** красный PR не мержится (или `KI-023` `Blocked` с ручным
   fallback); coverage-гейт; `gates --full` воспроизводит CI.
7. **Безопасность:** ASVS L1 без открытых High; секретов в конфигах нет;
   `KI-027` закрыт или сужен с планом.
8. **Документация:** ADR, runbook, SLO, capacity, upgrade, `CHANGELOG`,
   `RELEASES`, отчёты по шагам и спринтам; мёртвых ссылок нет.
9. **Релиз:** тег `v0.4.0`, GitHub/GitFlic Release, SBOM/checksums,
   post-release smoke и проверенный откат.

---

## 7. Критический путь и параллелизм

**Критический путь:** 33 → 34 → 35 → 36 → 41 (~15 инженерных дней).

| Волна | Спринты | Условие старта |
|-------|---------|----------------|
| 1 | 33 | v0.3.3; S33-001/002 уже закрыты |
| 2 | 34, 37 | 33; для 37 — доступ владельца по `KI-023` |
| 3 | 35, 38, 40 | 34 (38 также 33; 40 — по мере готовности) |
| 4 | 36, 39 | 35 (39 также 34) |
| 5 | 41 | все спринты 33–40 |

При одном разработчике «параллельные» ветки означают переключение между
задачами, а не одновременную работу. Действие владельца по `KI-023`
(агент/токен GitFlic или GitHub Pro) нужно начинать в начале этапа: это
самый длинный внешний lead time. Если доступ не появится, спринт 37
фиксируется как `Blocked`, а релиз v0.4.0 может выйти с ручным гейтом —
это явное решение, а не забытый пункт.

---

## 8. Риски и меры

| Риск | Вероятность | Влияние | Мера |
|------|-------------|---------|------|
| `KI-023`: нет доступа к GitFlic-агенту/GitHub Pro | Высокая | Высокое | Начать в волне 2; fallback — ручной гейт + `gates.ps1|sh`; не блокировать остальные спринты |
| Нестабильный PyPI/trivy DB/зеркала (`KI-017`) | Высокая | Среднее | wheelhouse, кэш, `--skip-db-update` по расписанию, повторяемые сборки |
| Digest upstream-образа исчез/перезаписан | Средняя | Среднее | `docker pull` + `inspect`, guard, документированная процедура обновления; не обновлять digest «попутно» |
| Мониторинг съедает ресурсы одного узла | Средняя | Среднее | Профиль `monitoring` опционален, лимиты CPU/RAM, retention Prometheus |
| Ограничения compose-мультиреплики | Высокая | Среднее | Sticky sessions, health-checks, явно описать границы; Kubernetes/Swarm — вне этапа |
| Off-site бэкап: утечка/потеря ключей | Средняя | Высокое | Шифрование, отдельные credentials, restore drill, ротация |
| `KI-027`: cookie/BFF не влезает в этап | Средняя | Низкое | В v0.4.0 — `token_version`/logout; cookie/BFF — v0.5, риск XSS зафиксирован |
| CI стал медленным/дорогим | Средняя | Среднее | Кэш, таймауты, path-фильтры, параллелизм, замер до/после |
| Флаки на Windows/self-hosted | Средняя | Среднее | Полный прогон в Linux-образе, skip-маркеры, без «слепых» retry |
| Документация расходится с кодом | Средняя | Низкое | env-drift тест, `check_version`, обновление docs в DoD каждого шага |

---

## 9. Границы этапа (что не входит в v0.4.0)

- Kubernetes, Docker Swarm, HA PostgreSQL/Redis (Sentinel/Cluster),
  multi-region и active-active.
- SSO/LDAP/SAML/SCIM, мультитенантность, биллинг и платежи.
- Мобильное приложение, PWA offline, новые языки интерфейса.
- Полный внешний пентест, WAF, SIEM; ASVS L1 — самостоятельная оценка с
  доказательствами, не сертификация.
- Перенос access/refresh-токенов в httpOnly-cookie/BFF — цель v0.5
  (в v0.4.0 закрывается `token_version` и logout); план — [TODO_V0.5.md](TODO_V0.5.md)
  S45-006.
- Подпись образов (cosign), SLSA Level 3, reproducible builds «бит-в-бит» —
  backlog; в v0.4.0 — digest, SBOM и сканы.
- Feature flags на пользователя, RAG v3/reranking, новые LLM-провайдеры.
- Email-deliverability (SPF/DKIM/DMARC) — эксплуатационная задача, не код.

---

## 10. Отчётность и правила обновления плана

- Каждый шаг — отдельный отчёт `docs/reports/sprint-N/STEP-MM_<ТЕМА>.md`
  по `RULES.md` §12 (7 разделов).
- Каждый спринт — `docs/reports/sprint-N/SPRINT-N.md` по `RULES.md` §2.4,
  запись в `docs/RELEASES.md` и `docs/CHANGELOG.md`.
- Статусы задач обновляются здесь сразу после шага; оценки уточняются по
  факту, а не «подгоняются» задним числом.
- Если задача выросла больше чем на ~20% или меняется порядок спринтов —
  обновить этот файл и добавить запись в §12 «Журнал изменений плана».
  Второй файл-план не создаётся.
- Новый блокер — сразу `KI-NNN` (следующий свободный — `KI-031`) и остановка
  шага; обходной путь фиксируется в KI и отчёте.

---

## 11. Вопросы на согласование

До старта шага 02 спринта 33 нужно подтвердить:

1. **Порядок и объём** спринтов 33–41 и оценки ~26 инженерных дней.
2. **Мониторинг:** Prometheus + Grafana + Loki в compose (профиль
   `monitoring`, по умолчанию выключен) — или внешний стек?
3. **Мультиреплика:** sticky sessions на nginx для WS — или Redis pub/sub;
   compose-мультиреплика — или сразу Swarm/K8s (последнее вне этапа).
4. **Единые команды:** `Makefile` + `scripts/tasks.ps1` (без новых
   зависимостей) — или Taskfile/`just`?
5. **`KI-027`:** `token_version` + logout в v0.4.0, cookie/BFF — в v0.5.
6. **`KI-023`:** начинаем с действия владельца; если доступа нет — релиз с
   ручным гейтом и `KI-023 Blocked`?
7. **Целевая дата v0.4.0** и приоритеты, если время ограничено: сначала
   критический путь 33→34→35→36→41, затем 37/38/39/40.

---

## 12. Журнал изменений плана

| Дата | Изменение |
|------|-----------|
| 2026-11-02 | Создан высокоуровневый план v0.4.0 (спринты 33–41), аудит практик, карта KI |
| 2026-11-05 | S33-001 (digest) и S33-002 (non-root) закрыты; добавлена детализация задач S33-003…S41-005, оценки, критический путь, риски, границы этапа и вопросы на согласование |
| 2026-11-05 | Создан план следующего этапа [TODO_V0.5.md](TODO_V0.5.md) (спринты 42–50); в этом файле обновлён следующий свободный KI (`KI-031`) и ссылка на cookie/BFF (S45-006) |
