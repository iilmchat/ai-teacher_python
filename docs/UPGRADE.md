# UPGRADE.md — обновление до v0.6.0

> **v0.5.0 → v0.6.0** (2026-11-11): «Auth & Edge Hardening» — breaking change
> `POST /auth/refresh` (токен в теле JSON), `is_active` в RBAC, trusted proxy,
> лимиты, fail-fast `SECRET_KEY`, `DOCS_ENABLED` — §0.5.
> **v0.3.3 → v0.5.0** (2026-11-10): релиз «Learning Experience & Teaching
> Workflow», миграции `014`–`022` — §0.
> **v0.3.2 → v0.3.3** (2026-11-05): метрики-события KI-024 и auth-hardening
> KI-026 — архив ниже.
> **v0.3.1 → v0.3.2** (2026-11-03): встроенный retention-планировщик и метрики
> retention — архив ниже.
> **v0.2.0 → v0.3.0** (2026-11-01): релиз «Ops & Scale» — CI/релиз-процесс,
> зависимости, песочница, наблюдаемость, приватность, поиск и инструменты
> учителя — архив ниже.

## 0. Обновление v0.3.3 → v0.5.0

Релиз v0.5.0 — **single-node**. Этап v0.4.0 «Production & Multi-node» отложен
(D-001), поэтому обновление выполняется сразу с v0.3.3. Все миграции
**аддитивные**: новые таблицы, колонки и индексы; существующие данные и
контракты API не переписываются. Проверено на чистой БД и на копии рабочей:
`upgrade head → downgrade base → upgrade head`, `alembic check` — без
расхождений.

### 0.1. Новые объекты БД (миграции 014–022)

| Миграция | Объект | Что добавляет | Назначение |
|----------|--------|---------------|------------|
| `014` | таблица `task_attempts` | `id`, `user_id→users`, `task_id→tasks`, `code`, `passed`, `passed_count`, `total_count`, `results JSONB`, `created_at`; индексы `(user_id, task_id, created_at)`, `(task_id, created_at)` | история засчитанных попыток (S42-002) |
| `015` | колонки `user_task_progress.draft_code`, `draft_updated_at` | `TEXT NULL`, `TIMESTAMP NULL` | автосохранение черновика решения (S42-003) |
| `016` | колонки `chat_sessions.title`, `pinned`; индекс `(user_id, pinned, updated_at)` | `VARCHAR(120) NULL`, `BOOLEAN NOT NULL DEFAULT false` | заголовки, переименование и закрепление чатов (S43-001) |
| `017` | таблица `message_feedback` | `id`, `message_id→chat_messages`, `user_id→users`, `value SMALLINT` (`CHECK value IN (-1,1)`), `comment VARCHAR(500) NULL`, `created_at`; `UNIQUE(message_id, user_id)`, индекс `(message_id)` | оценка ответов ассистента (S43-003) |
| `018` | колонка `users.token_version` | `INTEGER NOT NULL DEFAULT 0` | отзыв refresh-токенов при смене пароля и «выйти везде» (S45-001/005) |
| `019` | таблица `user_sessions` | `id`, `user_id→users`, `jti VARCHAR(36)` (`UNIQUE`), `user_agent`, `ip`, `created_at`, `last_used_at`, `revoked_at`; индекс `(user_id)` | активные сессии и их отзыв (S45-005) |
| `020` | таблица `attempt_feedback` | `id`, `attempt_id→task_attempts`, `teacher_id→users`, `comment TEXT`, `created_at`; `UNIQUE(attempt_id, teacher_id)`, индекс `(attempt_id)` | комментарий учителя к попытке (S46-002) |
| `021` | таблица `classroom_announcements` | `id`, `classroom_id→classrooms`, `author_id→users`, `title VARCHAR(200)`, `body TEXT`, `created_at`; индекс `(classroom_id, created_at)` | объявления класса (S46-006) |
| `022` | колонки `tasks.source`, `tasks.moderation_comment`; индекс `(source, created_at)` | `VARCHAR(20) NOT NULL DEFAULT 'manual'`, `TEXT NULL` | происхождение задачи и очередь модерации (S47-003) |

Все внешние ключи новых таблиц — `ON DELETE CASCADE` (удаление пользователя
или задачи уносит связанные попытки, оценки, сессии и комментарии). Существующие
задачи после `022` получают `source='manual'`; существующие пользователи —
`token_version=0`, поэтому выданные ранее токены продолжают работать.

Отдельно: миграции `014`–`022` не меняют типы существующих колонок и не
переименовывают таблицы. `downgrade` удаляет только добавленное (см. §0.5).

### 0.2. Порядок обновления

```bash
# 0) Зафиксировать, что именно обновляем
git fetch --tags && git checkout v0.5.0

# 1) Бэкап (обязательно: downgrade удаляет данные новых таблиц)
bash scripts/backup.sh

# 2) Переменные окружения: новых обязательных нет, одна опциональная (см. §0.3)
cp .env.example .env && $EDITOR .env

# 3) Миграции: 013 → 022
cd backend
alembic current                  # ожидается 013 (или 022, если уже обновляли)
alembic upgrade head
alembic check                    # "No new upgrade operations detected."
cd ..

# 4) Пересборка и запуск (single-node)
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# 5) Проверка
curl -fsS http://127.0.0.1:8000/health/ready
curl -fsS http://127.0.0.1:8000/api/v1/health
docker compose -f docker-compose.prod.yml ps
```

Если БД обновляется без простоя, сначала остановите backend, примените
миграции и поднимите новую версию: старый код совместим со схемой, но не
умеет читать новые данные и не должен писать в новые таблицы.

### 0.3. Переменные окружения

| Переменная | По умолчанию | Назначение |
|------------|--------------|------------|
| `RETENTION_TASK_ATTEMPTS_DAYS` | `90` | срок хранения истории попыток (`0` — не удалять); остальные `RETENTION_*` не менялись |

Новых обязательных переменных нет. Лимит пробных проверок
`POST /tasks/{id}/check` — 20 в минуту на пользователя (при превышении — 429
с `Retry-After`); это константа кода (`CHECK_LIMIT` в
`app/core/rate_limiter.py`), а не ENV. `VERSION` в `.env` по-прежнему не
задаёт версию приложения — она берётся из `backend/app/config.py` (теперь
`0.6.0`).

### 0.3.1. Новые переменные v0.6.0 (S34–S35)

| Переменная | По умолчанию | Назначение |
|------------|--------------|------------|
| `TRUSTED_PROXIES` | пусто | IP/CIDR reverse-proxy, которым доверяем `X-Forwarded-For` (S34-003); в prod-compose — `127.0.0.1` |
| `DOCS_ENABLED` | `true` | `false` убирает Swagger/ReDoc/OpenAPI (S34-006); в prod — `false` |
| `UVICORN_WORKERS` | `1` (prod — `2`) | число воркеров (S35-001) |
| `PROMETHEUS_MULTIPROC_DIR` | пусто | каталог multiprocess-метрик; в prod — `/tmp/prometheus-multiproc` |
| `METRICS_ENABLED` | `true` | публикация `/metrics` (S35-001); в prod обязателен |
| `SENTRY_DSN` / `SENTRY_ENVIRONMENT` / `SENTRY_TRACES_SAMPLE_RATE` / `SENTRY_RELEASE` | пусто / `development` / `0` / версия | ошибки и трейсы без PII (S35-002); пустой DSN — выключено |
| `GRAFANA_ADMIN_PASSWORD` | — | только для профиля `monitoring`; задать перед запуском |

Обязательных переменных по-прежнему нет, кроме production-секретов
(`SECRET_KEY`, `POSTGRES_PASSWORD`), которые проверяет `${VAR:?}` в
`docker-compose.prod.yml`.

### 0.4. Обратная совместимость API

Ломающих изменений нет; контрактный снапшот OpenAPI проходит проверку
«только аддитивные изменения» (`backend/tests/test_contract_openapi.py`).

- **Новые маршруты** не меняют поведение старых: `POST /tasks/{id}/check`,
  `GET /tasks/{id}/attempts`, `PATCH|DELETE /tasks/{id}/draft`,
  `PATCH /chat/sessions/{id}`, `POST .../messages/{id}/regenerate`,
  `POST|DELETE /chat/messages/{id}/feedback`, `GET /chat/sessions/{id}/export`,
  `GET /tasks/recommended`, `POST /users/me/password`,
  `GET /users/me/export`, `GET /users/me/sessions`,
  `PATCH /classrooms/{id}/assignments/{id}`, `.../members/bulk`,
  `.../announcements`, `GET /me/announcements`,
  `POST /me/notifications/read-all`, `GET /admin/tasks/review`,
  `POST /admin/tasks/{id}/moderate`, `GET /admin/quality` (расширен).
- **Новые поля в ответах аддитивны**: `title`/`pinned` у `ChatSession`,
  `draft_code`/`draft_updated_at` у `TaskDetail`, `source`/`moderation_comment`
  у `TaskAdminDetail`, `practice` у `SubmitResponse`, `by_level` и
  `top_problem_topics` у `GET /admin/quality`.
- **Новые поля в запросах опциональны**: `?status=` у `GET /tasks`, `type` у
  `GET /me/notifications`, `problem_threshold` у drill-down, `source`/
  `difficulty`/`threshold` у очереди модерации.
- **Токены**: пары получают claim `tv`; refresh-токены без `jti` (выданные до
  v0.5.0) принимаются один раз и получают строку `user_sessions`. Смена
  пароля/«выйти везде» увеличивают `token_version` и инвалидируют старые
  refresh-токены. Access-токены, как и раньше, живут до истечения срока.
- **Поведенческие изменения**: `DELETE /tasks/{id}` при наличии прогресса
  выполняет мягкое удаление (`is_active=false`); публикация/снятие задачи
  модератором сразу влияет на каталог ученика; `GET /tasks` кэшируется на
  60 с (сброс — при мутациях задач).

### 0.5. Ломающие изменения (v0.6.0)

- **S34-002**: `POST /auth/refresh` теперь принимает `refresh_token` в теле JSON,
  а не в query-параметрах (`?refresh_token=...`). Это breaking change для клиентов.
  Пример:

  ```json
  // Раньше:
  POST /api/v1/auth/refresh?refresh_token=eyJ...

  // Теперь:
  POST /api/v1/auth/refresh
  Content-Type: application/json

  {
    "refresh_token": "eyJ..."
  }
  ```

  **Миграция для фронтенда**: обновите `api.ts`, функция `refreshAccessToken` теперь
  использует `json({ refresh_token })` вместо `params({ refresh_token })`.

- **S34-001**: `require_role` теперь использует `get_current_active_user`, что
  означает, что деактивированный пользователь (с `is_active=false`) получает
  `401 Unauthorized` вместо `403 Forbidden` при попытке получить доступ к
  защищённым эндпоинтам. Это ожидаемое поведение и соответствует политике
  безопасности.

### 0.6. Откат

Есть два сценария — выбирайте по причине.

**v0.6.0 → v0.5.0.** Миграций нет, схема БД не менялась: достаточно вернуть
код и пересобрать контейнеры. Перед откатом убедитесь, что клиенты снова
умеют передавать refresh-токен в query (или откат выполняется вместе с
фронтендом v0.5.0).

```bash
git checkout v0.5.0
docker compose -f docker-compose.prod.yml up -d --build
# миграции не трогаем — их в v0.6.0 не было
```

**v0.5.0 → v0.3.3.** Есть два сценария.

**A. Откат только кода (рекомендуется).** Схема v0.5.0 аддитивна: приложение
v0.3.3 работает с ней, не замечая новых таблиц и колонок.

```bash
git checkout v0.3.3
docker compose -f docker-compose.prod.yml up -d --build
# миграции НЕ откатываем: новые данные остаются и не мешают старой версии
```

**B. Полный откат схемы** (нужен, только если требуется вернуть БД к
состоянию v0.3.3). **Удаляет** историю попыток, черновики, заголовки чатов,
оценки ответов, активные сессии, комментарии учителей, объявления и данные
модерации.

```bash
bash scripts/backup.sh                 # ещё раз, перед разрушительным шагом
git checkout v0.3.3
cd backend
alembic downgrade 013                  # 022 → 013
alembic check                          # на v0.3.3-моделях — чисто
cd ..
docker compose -f docker-compose.prod.yml up -d --build
```

Проверено: `downgrade base` и повторный `upgrade head` проходят; тест
`backend/tests/test_migrations.py` покрывает полный цикл и отдельно `022`
(существующая задача → `manual`, downgrade убирает колонки).

### 0.7. Проверка после обновления

1. `/health/ready` → `status: ready`; `/api/v1/health` → `version: 0.6.0`.
2. Старый пользователь входит; в профиле видны «Мои данные», «Активные
   сессии»; смена пароля не разлогинивает текущее устройство.
3. Ученик: «Пробная проверка» не увеличивает счётчик попыток; после
   «Отправить решение» появляется запись в истории; черновик переживает
   перезагрузку.
4. Чат: заголовок создаётся из первого вопроса, «Стоп» и «Повторить»
   работают, оценка сохраняется.
5. Учитель: вкладка «Работы» показывает код попытки, комментарий уходит
   ученику; объявление видно в «Моих заданиях».
6. Админ: `/admin/audit`, `/admin/moderation`, `/admin/quality` открываются;
   выгрузка аналитики скачивается; в шапке есть бейдж уведомлений.
7. `alembic check` — без расхождений; в логах нет `alembic`-ошибок.

### 0.7. Известные ограничения v0.5.0

См. `docs/reports/DEVOPS_AUDIT_2026-11.md` и `docs/KNOWN_ISSUES.md`.
Кратко: single-node (нет HA/DR/SLO 2.0), нет registry/CD и автоматических
TLS/бэкапов, refresh-токен передаётся в query string, rate limit обходится
подделкой `X-Forwarded-For`, нет e-mail-подтверждения и сброса пароля. Продукт
**не готов к публичному production**; для закрытого пилота нужны меры из
аудита (merge и артефакт, TLS, бэкапы, auth/anti-abuse, наблюдаемость).

---

## Архив: v0.3.1 → v0.3.2

Патч без миграций и ломающих изменений: приложение само применяет retention
(вместо cron) и отдаёт счётчики удалённых строк в Prometheus.

1. **Новые переменные окружения** (все опциональны):

| Переменная | По умолчанию | Назначение |
|------------|--------------|------------|
| `RETENTION_SCHEDULER_ENABLED` | `false` (в `docker-compose.prod.yml` — `true`) | фоновый планировщик retention |
| `RETENTION_SCHEDULER_AT` | `03:30` | время запуска, UTC, формат `HH:MM` |
| `RETENTION_SCHEDULER_BATCH_SIZE` | `1000` | размер батча удаления |

2. Если в `.env` осталась строка `VERSION=...` — удалить её: версия задаётся в
   `backend/app/config.py` (иначе `/health` покажет устаревшее значение).
3. Пересобрать backend:
   `docker compose -f docker-compose.prod.yml up -d --build`.
4. Проверка: `curl -s http://127.0.0.1:8000/metrics | grep retention_` — счётчики
   `retention_rows_deleted_total`/`retention_runs_total` присутствуют; при
   включённом планировщике в логах есть `retention_scheduler_started` и
   `retention_scheduler_wait`.

Откат: вернуть код на `v0.3.1` и пересобрать backend — планировщик исчезнет,
внешний cron (если настроен) продолжит работать.

---

## Архив: v0.3.2 → v0.3.3

Патч без миграций и изменений API; меняются имена метрик наблюдаемости и
поведение аутентификации для заблокированных аккаунтов.

1. **Метрики LLM/кэша переименованы** (KI-024): `llm_requests`/`llm_failures`/
   `llm_latency_ms`/`llm_tokens`/`llm_fallbacks`/`cache_hits`/`cache_misses`/
   `cache_errors` → `llm_requests_total{provider,model,status}`,
   `llm_latency_seconds`, `llm_first_token_seconds`, `llm_tokens_total{provider,kind}`,
   `llm_fallbacks_total{primary}`, `cache_*_total`. Обновите дашборды и алерты
   (список — `docs/DESIGN_ADMIN_AND_OPS.md` §10). Добавлен `app_build_info{version}`.
2. **Несколько воркеров (опция):** если запускаете `uvicorn --workers N`,
   задайте `PROMETHEUS_MULTIPROC_DIR` и пересоберите backend-образ: entrypoint
   чистит каталог перед стартом. Без этого флага поведение прежнее (один процесс).
3. **Аутентификация (KI-026):** `login`/`refresh` отклоняют неактивные аккаунты
   (`is_active=false`) — после удаления аккаунта refresh больше не работает.
   При старте с дефолтным или коротким `SECRET_KEY` пишется `insecure_secret_key`
   (не блокирует запуск). Email в логах маскируется.

---

## Архив: v0.2.0 → v0.3.0 — что меняется для эксплуатации

| Область | Изменение | Действие |
|---------|-----------|----------|
| БД | 3 новые миграции: `011` (audit_log), `012` (users.is_active), `013` (assignment_templates) | `alembic upgrade head` |
| Песочница | контейнерный режим `EXECUTOR_MODE=container` (опция) + пул воркеров | по желанию: собрать образ и включить |
| Метрики | `GET /metrics` (Prometheus) и `/health/live`/`/health/ready` | открыть только внутренней сети |
| Логи | JSON по умолчанию, `X-Request-ID` сквозной | настроить сбор логов |
| Аудит | журнал действий teacher/admin + `GET /admin/audit` | проверить доступ admin |
| Экспорт/ПДн | CSV/JSON-экспорт, retention-скрипт, `DELETE /auth/me` | задать `RETENTION_*`, прочитать `docs/PRIVACY.md` |
| Поиск | `RAG_MIN_SCORE`, backfill эмбеддингов | при включённом RAG — запустить backfill |
| Email | `NOTIFICATIONS_EMAIL_ENABLED` (по умолчанию off) | включить при готовом SMTP |

**Ломающие изменения:** отсутствующий `Authorization` теперь даёт **401** (было
403 — поведение Starlette 1.x); `users.is_active=false` блокирует вход;
`/metrics` не публикуется через nginx (404).

## Архив: v0.2.0 → v0.3.0 — порядок обновления

```bash
git fetch && git checkout v0.3.0

# 1) Бэкап
bash scripts/backup.sh            # pg_dump в backups/

# 2) Новые переменные окружения (.env) — см. таблицу ниже
cp .env.example .env && $EDITOR .env

# 3) Миграции (с 010 до 013)
cd backend && alembic upgrade head && alembic check && cd ..

# 4) Пересборка и запуск
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# 5) Проверка
curl -fsS http://127.0.0.1:8000/health/ready
curl -fsS -H 'X-Request-ID: upgrade-check' http://127.0.0.1:8000/health/live
docker compose -f docker-compose.prod.yml ps
```

Опционально (изоляция песочницы):

```bash
docker build -f backend/sandbox_runner/Dockerfile -t ai-teacher-sandbox-runner:latest backend
docker run --rm -i --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges --user 65534:65534 \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m --memory 128m --pids-limit 64 \
  --pull never ai-teacher-sandbox-runner:latest --self-check
# затем EXECUTOR_MODE=container в .env
```

## Архив: v0.2.0 → v0.3.0 — новые переменные окружения

| Переменная | По умолчанию | Назначение |
|------------|--------------|------------|
| `EXECUTOR_MODE` | `native` | `native` или `container` (раннер в Docker) |
| `EXECUTOR_IMAGE` | `ai-teacher-sandbox-runner:latest` | образ раннера |
| `EXECUTOR_POOL_SIZE` | `2` | тёплые воркеры (0 — выключить) |
| `EXECUTOR_POOL_MAX_TASKS` | `50` | задач на воркер до перезапуска |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / `json` | логи (`console` — для dev) |
| `METRICS_ENABLED` / `METRICS_PATH` | `true` / `/metrics` | Prometheus-эндпоинт |
| `RETENTION_CHAT_MESSAGES_DAYS` | `90` | хранение сообщений чата (0 — off) |
| `RETENTION_CODE_EXECUTIONS_DAYS` | `90` | хранение запусков кода |
| `RETENTION_NOTIFICATIONS_DAYS` | `180` | хранение уведомлений |
| `RETENTION_AUDIT_LOG_DAYS` | `365` | хранение журнала аудита |
| `EXPORT_MAX_ROWS` | `100000` | лимит строк одного экспорта |
| `RAG_MIN_SCORE` | `0.0` | порог семантического поиска (0 — без порога) |
| `NOTIFICATIONS_EMAIL_ENABLED` | `false` | email-уведомления |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` | — | SMTP |
| `NOTIFICATIONS_DEADLINE_HOURS` | `72` | окно напоминаний о дедлайне |

Полный список — `.env.example`.

## Архив: v0.2.0 → v0.3.0 — после обновления

1. `/health/ready` → `status: ready`; `/metrics` отдаёт метрики.
2. Аудит: действие учителя (создание задачи) видно в `GET /api/v1/admin/audit`.
3. Retention: `python backend/scripts/apply_retention.py --dry-run` (ничего не удаляет).
4. RAG (если включён): `python backend/scripts/backfill_embeddings.py --dry-run`, затем без флага.
5. Email (если включён): назначить задачу классу — письмо в SMTP/MailHog.

## Архив: v0.2.0 → v0.3.0 — откат

```bash
# вернуть код
git checkout v0.2.0
# откатить миграции (011–013 аддитивные, данные новых таблиц будут удалены)
cd backend && alembic downgrade 010 && cd ..
docker compose -f docker-compose.prod.yml up -d --build
```

`010 → 009` и ниже не требуется: новые таблицы/колонки не использовались старой
версией. Перед откатом сделайте бэкап: `bash scripts/backup.sh`.

## Архив: v0.2.0 → v0.3.0 — известные ограничения

См. [KNOWN_ISSUES.md](KNOWN_ISSUES.md): KI-023 (branch protection на GitHub Free),
KI-018 (`.format()` в песочнице), KI-027 (токены в localStorage; httpOnly-cookie
— v0.6.0). KI-024 закрыта в v0.3.3 (метрики-события), KI-025 (retention по cron)
закрыта в v0.3.2 — теперь есть встроенный планировщик.
