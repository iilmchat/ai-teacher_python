# CHANGELOG.md — История версий

Все заметные изменения в проекте документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
и проект следует [Semantic Versioning](https://semver.org/lang/ru/).

---

## [Unreleased]

### Документация
- `TODO_V0.4.md` детализирован: задачи `S33-001`…`S41-005`, зависимости,
  оценки, DoD, критический путь, риски и границы этапа; статусы и карта KI
  приведены к состоянию после шага 01 спринта 33.
- Создан `TODO_V0.5.md` — план этапа v0.5.0 «Learning Experience & Teaching
  Workflow» (спринты 42–48): аудит продукта по 7 срезам (ученик, чат,
  песочница, аккаунт, учитель, админ, платформа), задачи `S42-001`…`S48-003`,
  зависимости, оценки, DoD, риски, границы этапа и решения владельца.
- Создан `TODO_V0.6.md` — план этапа v0.6.0 «Engagement, Accessibility & Auth
  Hardening» (спринты 49–52): траектории и вовлечение, доступность и PWA,
  перенос токенов в httpOnly-cookie/BFF (закрывает `KI-027`), релиз.
- Заведены `KI-028` (нет смены пароля и управления сессиями), `KI-029`
  (`best_solution` не читается), `KI-030` (часть API не покрыта UI).

### Добавлено
- Пробная проверка решения без траты попытки (S42-001, спринт 42):
  `POST /api/v1/tasks/{id}/check` прогоняет тест-кейсы в песочнице, но не
  меняет счётчик попыток и статус задачи, не создаёт запись прогресса и не
  начисляет достижения; в ответе `practice: true`. Лимит — 20 пробных
  проверок в минуту на пользователя (429 с `Retry-After`). В интерфейсе —
  кнопка «Пробная проверка» с подсказкой «не засчитывается в попытки».
- Заголовки и управление сессиями чата (S43-001, спринт 43): в
  `chat_sessions` появились `title` (nullable, авто-заголовок из первого
  вопроса, до 60 символов) и `pinned` (миграция `016`, индекс
  `(user_id, pinned, updated_at)`). API: `PATCH /api/v1/chat/sessions/{id}` —
  переименование и закрепление сессии; `GET /api/v1/chat/sessions` —
  закреплённые сверху, остальные по `updated_at`. В интерфейсе — заголовок в
  списке чатов, переименование, закрепление и удаление с подтверждением.
- Остановка генерации и регенерация ответа (S43-002, спринт 43): в чате
  появилась кнопка «Стоп» — сервер прерывает поток по команде
  `{"type":"stop"}`, сохраняет частичный ответ с пометкой `stopped` и
  присылает `{"type":"stopped"}`. API:
  `POST /api/v1/chat/sessions/{id}/messages/{message_id}/regenerate` — новый
  ответ на тот же вопрос с тем же уровнем; вопрос не дублируется, прежний
  ответ остаётся в истории с пометками `replaced` и `replaced_by`.
- Сторы вынесены в отдельный чанк сборки: entry-бандл 79.98 → 69.51 kB
  gzip (лимит 80 kB — `docs/ARCHITECTURE.md`).

### Добавлено
- История попыток по задачам (S42-002, спринт 42): таблица
  `task_attempts` (миграция `014`) хранит код, результат по каждому
  тест-кейсу и время каждой засчитанной отправки. API:
  `GET /api/v1/tasks/{id}/attempts` (постранично, новые сверху) и
  `GET /api/v1/tasks/{id}/attempts/{attempt_id}` (код и разбор).
  Попытки видны только их автору. В интерфейсе — блок «История попыток»
  с разбором и возможностью вернуть код в редактор. Retention:
  `RETENTION_TASK_ATTEMPTS_DAYS` (по умолчанию 90).
### Добавлено
- Автосохранение черновика решения (S42-003, спринт 42): колонки
  `draft_code` и `draft_updated_at` в `user_task_progress` (миграция
  `015`). API: `PATCH /api/v1/tasks/{id}/draft` и `DELETE
  /api/v1/tasks/{id}/draft`. Черновик сохраняется между сессиями и
  восстанавливается при открытии задачи; в интерфейсе — индикатор
  «Черновик сохранён» и кнопка «Удалить черновик». Черновик не является
  решением: попытку не засчитывает и в историю попыток не попадает.
### Добавлено
- Поиск и фильтры каталога задач (S42-004, спринт 42): строка поиска,
  фильтры категории, тега и статуса, счётчик найденного, сброс фильтров.
  Фильтры сохраняются в query-параметрах URL — ссылкой можно поделиться.
  На сервере добавлен фильтр `GET /tasks?status=...`: он отбирает задачи по
  прогрессу конкретного ученика. Поиск отправляется с задержкой 300 мс,
  устаревшие запросы каталога отменяются.
### Добавлено
- Рекомендация следующей задачи (S42-005, спринт 42):
  `GET /api/v1/tasks/recommended` подбирает до 5 задач, которые стоит
  решить дальше, — по прогрессу ученика: сначала начатые, потом задачи той
  же темы, потом следующий шаг по сложности. Порядок детерминированный,
  у каждой рекомендации есть пояснение. В интерфейсе — блок
  «Рекомендуем дальше» на дашборде и на странице задачи.

### Добавлено
- Связка задачи и ассистента (S42-006, спринт 42): deep-link
  `/chat?task=<id>` и кнопка «Спросить ассистента» на странице задачи и в
  результатах проверки. Сервер получает только `task_id`, сам загружает
  условие активной задачи и передаёт его ассистенту отдельным системным
  сообщением — без эталонного решения, ожидаемых выводов и подсказок.
  В `content` сообщения остаётся только вопрос, в `message_metadata` —
  `task_context {task_id, title}`. В чате показывается плашка контекста с
  кнопкой «Убрать»; REST и WebSocket поддерживают `task_id`.

### Безопасность
- Supply chain (S33-001/S33-002): базовые образы (`python`, `node`, `nginx`,
  `pgvector`, `redis`) закреплены по digest; backend работает под non-root
  `app` (UID/GID 10001), `/app` для процесса read-only. Guard
  `backend/scripts/check_image_pins.py` проверяет пиннинг в lint-джобе.

## [0.3.3] — 2026-11-05

Патч наблюдаемости и безопасности: метрики-события и multiprocess-экспортёр
(KI-024), auth-hardening (KI-026), лицензия и политика безопасности. План
v0.4.0 — в [TODO_V0.4.md](../TODO_V0.4.md).

### Добавлено
- Общий экспортёр метрик (KI-024): multiprocess-режим `prometheus_client`
  (`PROMETHEUS_MULTIPROC_DIR`) — при `uvicorn --workers N` любая реплика отдаёт
  общий агрегат; каталог чистит `docker-entrypoint.sh` перед стартом
- `app_build_info{version}` в `/metrics`
- `LICENSE` (MIT), `SECURITY.md` (политика безопасности), `TODO_V0.4.md`
  (план v0.4.0, спринты 33–41)
- Тесты: `tests/test_metrics_export.py`, `tests/test_auth.py` (+3)

### Изменено
- Версия 0.3.3
- Метрики LLM/кэша стали событиями (KI-024): `llm_requests_total{provider,model,status}`,
  `llm_latency_seconds`, `llm_first_token_seconds` (гистограммы),
  `llm_tokens_total{provider,kind}`, `llm_fallbacks_total{primary}`,
  `cache_*_total` вместо per-process gauge — значения складываются между воркерами
- Удалены мёртвые зависимости `aioredis`, `testcontainers`
- `.env.example`: добавлены `METRICS_*`, `CACHE_*` и `PROMETHEUS_MULTIPROC_DIR`

### Исправлено
- KI-026 (безопасность): неактивный аккаунт больше не входит и не обновляет
  токены; `bcrypt` вынесен в поток (не блокирует event loop); при старте
  предупреждение о дефолтном `SECRET_KEY`; email в логах маскируется
- KI-024 переведён в `Resolved`

### Безопасность
- `POST /auth/login` и `/auth/refresh` проверяют `is_active` (KI-026)
- `LoggingEmailSender` маскирует адрес получателя (PII, PRIVACY.md)

## [0.3.2] — 2026-11-03

### Добавлено
- Встроенный планировщик retention (KI-025): при `RETENTION_SCHEDULER_ENABLED`
  приложение раз в сутки (`RETENTION_SCHEDULER_AT`, UTC) само применяет
  `RETENTION_*_DAYS`; cron на хосте становится опциональным. На время прогона
  берётся advisory-lock PostgreSQL — при нескольких инстансах двойного запуска
  нет; остановка приложения даёт доиграть текущий прогон
- Prometheus-счётчики retention: `retention_rows_deleted_total{table}` и
  `retention_runs_total{table,result}` (в т.ч. для CLI-запусков)

### Изменено
- Версия 0.3.2; в `docker-compose.prod.yml` планировщик включён по умолчанию
- `.env.example`: убрана переменная `VERSION` (перекрывала версию из
  `backend/app/config.py` и устаревала при каждом релизе); добавлены
  `RETENTION_SCHEDULER_*`
- Документация: актуализированы чекбоксы TODO (UI-остатки 26/28 уже сделаны),
  шапки TODO/RELEASES, UPGRADE, PRIVACY, DESIGN_ADMIN_AND_OPS

## [0.3.1] — 2026-11-01

### Добавлено
- UI шаблонов назначений: список, создание из выбранных задач, применение к
  классу и удаление на странице класса (`AssignmentTemplates`); закрыт последний
  API-only пробел после v0.3.0
- 4 frontend-теста на шаблоны (список/применение, сохранение, удаление, ошибка)

### Изменено
- Версия 0.3.1; release-заметки — раздел «Релиз v0.3.1» в RELEASES

## [0.3.0] — 2026-11-01 «Ops & Scale»

Этап v0.3.0 (спринты 21–30): CI и релиз-процесс, современные зависимости,
производительность и изоляция песочницы, наблюдаемость, приватность, поиск,
инструменты учителя и завершение UX/a11y/i18n.

### Добавлено
- Наблюдаемость: `X-Request-ID`, структурированные логи (JSON), `/metrics`
  (Prometheus), `/health/live` и `/health/ready`
- Аудит действий teacher/admin: `audit_log` (миграция 011) и `GET /admin/audit`
- Экспорт: `GET /admin/analytics/export` (CSV/JSON), `GET /classrooms/{id}/report`,
  `GET /classrooms/{id}/gradebook` (+`/csv`); retention-скрипт и `RETENTION_*`
- Приватность: `DELETE /auth/me` (анонимизация, `users.is_active` — миграция 012),
  `docs/PRIVACY.md`
- RAG v2: `RAG_MIN_SCORE`, backfill эмбеддингов, панель поиска в чате
- Учителю: массовые назначения, шаблоны назначений (миграция 013), журнал
  оценок, email-уведомления за флагом
- UX: адаптивные таблицы-карточки, аудит локализации в CI, axe-контраст (light/dark)
- Песочница: контейнерный раннер (`EXECUTOR_MODE=container`) с self-check изоляции,
  пул воркеров и батч-исполнение

### Изменено
- FastAPI 0.162 / Starlette 1.x: отсутствующий `Authorization` → 401 (было 403)
- Логи по умолчанию — JSON, режим `console` — для разработки
- Compose healthcheck использует `/health/ready`

### Исправлено
- Windows: `docker.exe` вместо extension-less shim (WinError 193)
- Контейнерный батч: чтение stderr после kill (устранён hang)
- Async-тесты: фейковые исполнители реализуют `execute_many`

### Безопасность
- 0 открытых уязвимостей в зависимостях (`pip-audit`, OSV fallback)
- `/metrics` и `/health/*` не публикуются через nginx
- Аудит без PII; удаление аккаунта необратимо и логируется

## [0.3.0] — детали спринтов 19–30

Подробные записи по спринтам, вошедшим в v0.2.0 («Classroom») и v0.3.0
(«Ops & Scale»); выше — сводка релизов.

### Добавлено

**UX, A11y и локализация (S29)**

- Адаптивные таблицы: на `<640px` строки превращаются в карточки с подписями
  колонок (`Table`/`Tr`/`Td`/`Th`), без горизонтального скролла
- Локализация: все RU-fallback убраны из кода (`api.ts`, `auth.ts`,
  `chatSocket.ts`, сторы, `Spinner`) → ключи `errors.*`/`common.loading`
- Аудит локализации `scripts/check-i18n.mjs` в CI (кириллица вне локалей,
  паритет ключей ru/en)
- Playwright + `axe-core`: контраст WCAG AA на ключевых страницах в светлой и
  тёмной теме — 0 нарушений; e2e skip-link/меню/карточек

**Teacher & Classroom v3 (S28)**

- `POST /classrooms/{id}/assignments/bulk` — идемпотентные массовые назначения
  (`{created, skipped, unknown}`), уведомления только по новым
- Шаблоны назначений: таблица `assignment_templates` (миграция 013) и
  `/teacher/assignment-templates` (создание/список/удаление, применение к классу)
- `GET /classrooms/{id}/gradebook` + `/gradebook/csv` — журнал оценок с
  `completed_at` и `overdue`
- Email-уведомления за флагом `NOTIFICATIONS_EMAIL_ENABLED` (SMTP, best-effort)

**RAG v2 и поиск (S27)**

- `RAG_MIN_SCORE` — порог релевантности семантической выдачи; пустая выдача
  после фильтра уходит в ILIKE-fallback
- `scripts/backfill_embeddings.py` + `app/services/backfill.py`: идемпотентный
  backfill (батчи, лимит, dry-run, продолжение после ошибок провайдера)
- UI поиска в `ChatPage`: панель «Поиск по чату», подсветка `<mark>`,
  aria-live, i18n ru/en; e2e-сценарий
- Фикстуры `tests/fixtures/rag_queries.json` + precision@k тест

**Данные и приватность (S26)**

- `GET /api/v1/admin/analytics/export` — CSV/JSON, потоково, лимит
  `EXPORT_MAX_ROWS`, аудит каждого экспорта
- `GET /api/v1/classrooms/{id}/report` — CSV-матрица класса (overdue, итоги),
  только владельцу/админу
- Retention: `RETENTION_*_DAYS` + `backend/scripts/apply_retention.py`
  (`--dry-run`, батчи, `--only`)
- `DELETE /api/v1/auth/me` — удаление аккаунта с подтверждением паролем:
  анонимизация, блокировка входа (`users.is_active`, миграция 012)
- `docs/PRIVACY.md` — политика ПДн: состав, сроки, экспорт, удаление

**Наблюдаемость и аудит (S25)**

- `X-Request-ID` (входящий или `uuid4`) в ответе, в structlog-контексте и во
  всех записях логов; middleware пишет `http_request` с методом, путём, статусом
  и длительностью
- `GET /metrics` (Prometheus): HTTP, песочница, LLM, кэш, пул БД; LLM/кэш —
  gauge из счётчиков процесса; в nginx `/metrics` и `/health/*` → 404
- `/health/live` (процесс) и `/health/ready` (БД, Redis, конфиг LLM; 503 при
  недоступности); `/api/v1/health` сохранён; compose healthcheck → readiness
- Аудит `audit_log` (миграция 011) + `GET /api/v1/admin/audit` (фильтры,
  пагинация): роли, задачи, классы, назначения, удаление; best-effort запись
- `LOG_LEVEL`/`LOG_FORMAT` в конфиге (JSON по умолчанию, console — dev)

**Изоляция песочницы (S24)**

- Контейнер-раннер `ai-teacher-sandbox-runner` (`backend/sandbox_runner`):
  python:3.12-slim + RestrictedPython + чистое ядро песочницы, non-root;
  запуск `--network none --read-only --cap-drop ALL --security-opt
  no-new-privileges --user 65534:65534 --tmpfs /tmp --memory`
- `EXECUTOR_MODE=native|container` (по умолчанию `native`), `EXECUTOR_IMAGE`;
  при недоступном Docker/образе — fallback на native + warning и метрика
  `fallbacks`
- `--self-check` изоляции (uid, read-only rootfs, tmpfs, сеть, `CapEff=0`);
  проверяется в CI (`Docker build`) и `scripts/ci/docker.ps1`
- Метрики контейнерного режима (`runs`, `errors`, `timeouts`, `fallbacks`,
  среднее время старта) — основа для `/metrics` в S25

**Производительность песочницы (S23, KI-022)**

- Батч тест-кейсов: все кейсы задачи выполняет **один** дочерний
  интерпретатор (построчный JSON-протокол, таймаут на кейс). Submit 5 RPS:
  p95 **2219.7 → 395.0 мс**
- Пул тёплых интерпретаторов (`EXECUTOR_POOL_SIZE`, `EXECUTOR_POOL_MAX_TASKS`):
  переиспользование процесса между задачами, перезапуск после 50 задач и
  после `TimeoutError`/`MemoryError`/сбоя; закрытие в `lifespan`. Submit
  5 RPS: p95 **48.9 мс**, p50 34.8 мс
- Нагрузочные гейты: job `Perf smoke (submit)` (0.5 RPS на PR) и ночной
  `perf-nightly.yml` (2 RPS); отчёт `docs/reports/sprint-23/LOAD_TEST-SUBMIT.md`
- Тесты: батч (16), пул (11), безопасность батча/пула (36: 14 атакующих
  векторов × 2 режима + восстановление после MemoryError/TimeoutError)
**Контрактные тесты и зависимости (S22)**

- Снапшот OpenAPI (`backend/tests/contracts/openapi.json`, 68 операций,
  92 схемы) и тест совместимости: разрешены только аддитивные изменения
  (`backend/tests/contract_utils.py`); перегенерация —
  `python scripts/snapshot_openapi.py`
- Фикстуры форм ответов 21 ключевого эндпоинта (auth, tasks, chat, classrooms,
  admin analytics) — `backend/tests/test_api_contract_shapes.py` +
  `contracts/endpoints.json`
- `fastapi 0.162.0` + `starlette 1.10.0` (KI-015): 7 advisory starlette
  закрыты, `pip-audit` в CI — без `--ignore-vuln`
- `pytest 9.2.0`, `pytest-asyncio 1.4.1`, `pytest-cov 7.1.0`,
  `pytest-env 1.8.3` (KI-016): dev-only advisory PYSEC-2026-1845 закрыт

**CI (S21)**

- CI снова запускает проверки: workflow `CI (self-hosted fallback)` на
  Windows-runner'е (`C:\actions-runner`) — `Lint (backend)`, `Test (backend)`,
  `Frontend`, `Security`, `E2E (Playwright)`, `Docker build`; прогон 6/6
  зелёный, минуты GitHub не расходуются (KI-014)
- Переиспользуемый набор гейтов (`workflow_call`) — его же вызывает релиз,
  команды не дублируются
- Path-фильтры: docs-only PR не гоняет e2e/docker (GitHub `paths-ignore`,
  GitFlic `rules: changes:`)
- Офлайн-путь зависимостей для CI: wheelhouse в named volume
  `ai-teacher-wheelhouse` (`scripts/ci/build-wheelhouse.ps1`,
  `scripts/ci/install-python-deps.sh`) + постоянные кэши pip/pnpm — job'ы не
  зависят от нестабильного PyPI (KI-017)
- Релиз одной командой: `.github/workflows/release.yml` (гейты → тег →
  GitHub Release), dry-run по умолчанию, репетиция по тегу `v*-dryrun`,
  заметки — из `docs/RELEASES.md`
- `scripts/ci/protect-branch.ps1` — готовая защита ветки (6 required checks,
  запрет force-push) с честной диагностикой 403 на GitHub Free/private
- GitFlic: полный `gitflic-ci.yaml` (5 job'ов + 3 security + e2e/docker на
  PowerShell-агенте + тег-джоб `release`), пилотный `ci/gitflic-pilot.yaml`,
  рунбук `docs/GITFLIC_RUNNER.md`, настройка проекта `scripts/gitflic/setup.ps1`
- `docs/CI.md` — платформа, гейты, релиз, эксплуатация runner'а; RULES §11.20

### Изменено

- **401 вместо 403 без заголовка `Authorization`** (S22-002, Starlette 1.x):
  поведение выровнено по RFC 7235 (`401` + `WWW-Authenticate`); клиентский код
  уже обрабатывал 401 (refresh/логин). Переводы ошибок и SPEC §7 обновлены.
- `pytest`/`ruff`/`mypy` в CI ставятся из `backend/requirements.txt`
  (закреплённые версии): unpinned ruff давал 54 ложных ошибки на неизменённом
  коде, а mypy без runtime-зависимостей — 295 `import-not-found`
- GitHub-hosted `ci.yml` переведён в ручной режим до восстановления биллинга
  (KI-014) — красный workflow больше не висит на каждом PR
- `E2E_PYTHON` для runner'а указывает на актуальный venv проекта

---

## [0.2.0] - 2026-10-30

Релиз «Classroom»: классы и назначения, достижения и дашборд, UX/тёмная
тема, производительность (S19) и безопасность/эксплуатация (S20).

### Добавлено

**Производительность и масштаб (S19)**

- Redis-кэш справочников (`/chat/levels`, `/tasks/categories`) и каталога
  задач (`/tasks`): TTL 60 с, ключ включает пользователя и все фильтры,
  инвалидация при CRUD/импорте/seed/откате версии; fail-open и 10-секундное
  «остывание» после сбоя Redis; метрики `cache` в `/admin/analytics`
- Пагинация `GET /classrooms`, `GET /me/notifications`, `GET /teacher/tasks`
  (`total` — по всей таблице, а не по странице); N+1 в классах устранены
  одним агрегирующим запросом
- Индексы миграции 0009 под каталог/учеников/уведомления/дедлайны/историю
  сообщений; HNSW-индекс `chat_messages.embedding` (миграция 0010)
- Поиск по истории чата `GET /chat/search` (RAG-lite): семантический режим
  (pgvector, HNSW) за флагом `RAG_ENABLED`, ILIKE-фолбэк, только свои
  сообщения; best-effort эмбеддинги — сбой провайдера не ломает чат
- Нагрузочный тест S19-006 (httpx-генератор вместо k6/locust — PyPI с хоста
  заблокирован): `health` 50 RPS — p95 **6.3 мс**, каталог 20 RPS — p95
  **25.4 мс** (0 ошибок, PASS); `submit` — knee ≈2 RPS, целевые 5 RPS не
  достигнуты (факт 2.5 RPS, p95 2219.7 мс при бюджете 2000 мс) — ограничение
  песочницы, **KI-022**, рекомендации в `reports/sprint-19/LOAD_TEST.md`
- Локальный Monaco без CDN: ассеты `public/monaco/vs`, lazy-чанк,
  `pnpm test:offline` (KI-013)
- Code splitting всех маршрутов: vendor-чанки; entry — 76.3 kB gzip на S19-002,
  **78.71 kB gzip** после финальной сборки v0.2.0 (лимит 80)

**Безопасность и эксплуатация (S20)**

- Аудит зависимостей: `pnpm audit` — **0** уязвимостей; backend — **0
  critical**, остаточные записи (`starlette`, dev `pytest`) приняты и
  задокументированы (KI-015, KI-016)
- `python-jose` удалён → **PyJWT 2.15.1**; `python-multipart` 0.0.17 → **0.0.31**
- RestrictedPython 7.4 → **8.5**: закрыты 3 high-обхода песочницы; `.format()`
  и `string.Formatter` теперь запрещены с понятной подсказкой
  (`error_type=RestrictedFeatureError`)
- `.gitleaks.toml` + CI job `Security` (`pip-audit`, `gitleaks`,
  `pnpm audit`); `.github/dependabot.yml` (pip/npm/github-actions, weekly)
- nginx: CSP + `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy`, `HSTS`; `server_tokens off`;
  `ALLOWED_ORIGINS` в prod-compose — из ENV
- `scripts/backup.sh` и `scripts/restore.sh`: бэкап через
  `docker exec pg_dump` + gzip + sha256, retention, guard от перезаписи
  рабочей БД; smoke — 14/14 таблиц восстановлено
- `backend/scripts/audit_python_deps.py` — офлайн-аудит по GitHub Advisory
  API для машины без PyPI (лимит 60 запросов/час, кэш, `--resume`)
- `/tasks/{id}/hints/{index}` требует аутентификации (S20-003, находка F1);
  автотест матрицы доступа `backend/tests/test_access_matrix.py` — **35 тестов,
  IDOR не найден** (отчёт `docs/reports/sprint-20/ACCESS_MATRIX.md`)
- Финальная документация v0.2.0: SPEC, CHANGELOG, RELEASES, KNOWN_ISSUES,
  RULES §11.18–11.19, MANUAL_TESTING_GUIDE, отчёты sprint-19/sprint-20

**Функциональность и UX (S11–S18)**

- Тёмная тема: переключатель в шапке/профиле, `localStorage`, Monaco `vs-dark`
- Дизайн-система: токены, `Modal`, `Toast`, `Tabs`, `Table`, `Badge`,
  `Skeleton`; dev-страница `/dev/ui` вне прод-бандла
- Доступность: skip-link, aria-разметка, `vitest-axe` на входе/регистрации
- Мобильное меню и drawer сессий чата
- Достижения (`achievements`, `user_achievements`, миграция 008): 6 правил,
  выдача при submit, `GET /me/achievements`
- `GET /me/stats`: решено, серия дней (UTC+3), средние попытки, активность в чате
- Дашборд `/dashboard`: прогресс-бар, streak, последние задачи, достижения
- In-app уведомления (`notifications`): назначение, дедлайн ≤72 ч, достижение;
  `GET /me/notifications` и отметка прочитанным
- Классы: `classrooms`, `classroom_members`, `assignments` (миграция 007);
  создание, вступление по коду, исключение участника
- Назначения задач классу с дедлайнами, `/me/assignments`, матрица прогресса
  класса; UI `/classrooms`, `/classrooms/:id`, `/assignments`
- Кабинет учителя: `/teacher/tasks` (CRUD, тест-кейсы, импорт с предпросмотром)
  и `/teacher/students` (агрегаты и прогресс по задачам)
- API учителя: `/teacher/tasks`, `/teacher/students`,
  `/teacher/students/{id}/progress`; импорт файла `/tasks/import/file`
- Импорт/экспорт задач: JSON и YAML, `POST /tasks/import`,
  `GET /tasks/export?format=json|yaml`, CLI `scripts/import_tasks.py`
- `SEED_ON_START=true` — идемпотентное наполнение задач при старте (KI-010)
- Генерация задач через LLM: `POST /tasks/generate`, проверка эталонного
  решения в песочнице, отчёт `created/rejected`
- Теги задач (`tasks.tags`, GIN-индекс) и поиск `?tag=&q=`,
  `GET /tasks/categories`
- История версий задач (`task_versions`), `GET /tasks/{id}/versions` и откат
- Живой прогон LLM_EVAL на DeepSeek: 15 ответов, оценки basic 0.99 /
  intermediate 0.93 / advanced 0.96; отчёт `docs/reports/llm-eval/2026-10-29/`
- `LM_STUDIO_MODEL` — имя локальной модели; `qwen/qwen3-4b-2507` проверен
  как fallback на `127.0.0.1:8034`
- Лимит памяти песочницы в дочернем процессе: `RLIMIT_AS` на POSIX,
  Job Object на Windows; `EXECUTOR_MEMORY_LIMIT` подхватывается (KI-009)
- Ограничение одновременных запусков: `EXECUTOR_MAX_CONCURRENCY`,
  `EXECUTOR_QUEUE_TIMEOUT`, 503 при перегрузке
- Обрезка вывода `EXECUTOR_MAX_OUTPUT` с пометкой `output_truncated`
- 14 тестов-атак: сеть, файлы, `__builtins__`, `getattr`, dunder
- Healthcheck LLM в `/api/v1/health`: статус `ok` / `degraded` / `not_configured`,
  провайдер, модель, fallback; ping с кэшем 60 с, ключ не раскрывается
- Fallback провайдеров: `LLM_FALLBACK_PROVIDER`, один повтор, 503 при отказе обоих
- Метрики LLM в памяти процесса: запросы, ошибки, latency, первый токен, токены;
  секция `llm` в `/admin/analytics` и карточка в админке
- Детектор «готового решения» для базового уровня: `warnings` в REST/WS,
  лог `level_policy_warning`
- Версии промптов (`prompts/versions.json`) и метаданные ответа
  (`provider`, `model`, `prompt_version`, `warnings`) в истории чата
- Миграция 004: `chat_messages.metadata` JSONB
- Инструмент прогона LLM_EVAL: `scripts/run_llm_eval.py` (Q1–Q5 × 3 уровня)
- E2E-тесты Playwright (12 сценариев): auth, чат, песочница, задачи, запрет админки
- Детерминированный LLM-провайдер `echo` для e2e и демо без ключа (`LLM_PROVIDER=echo`)
- Rate limiting в рантайме: Redis-клиент, middleware, 429 + `Retry-After`, fail-open
- Интеграционные тесты WebSocket-стриминга (протокол `start/token/done`)
- Тесты миграций Alembic: upgrade на пустую БД, сверка с моделями, downgrade→upgrade
- Скрипт `scripts/check_ports.py` — проверка портов и «своей» БД
- Пороги покрытия: backend 70% (факт 81), frontend 70/60/70 (факт 74/78/84)
- Job `e2e` в CI (Playwright + отдельная БД)

### Изменено
- WS-протокол вынесен в `serve_chat_socket`; эндпоинт получает сессию и
  провайдера через `Depends` (тестируемость)
- `pytest`-маркеры `slow` и `migrations`; полный backend-прогон ~59 с
- WS-сообщение `done` содержит `warnings` политики уровня
- `/code/limits` отдаёт лимиты памяти, вывода и параллелизма; результат
  выполнения — `memory_limit_enforced` / `output_truncated`
- Задачи: `tags` в ответах API, `q`/`tag` в каталоге, `PyYAML` в зависимостях
- Frontend: `@monaco-editor/react` удалён, используется `monaco-editor` с
  локальными AMD-ассетами и `MonacoEditor` lazy-чанком
- `/admin/analytics` расширен секцией `cache` (hits/misses/hit_rate/sets/
  invalidations/errors)
- Списочные эндпоинты получили аддитивную пагинацию (`skip`/`limit`),
  дефолты сохраняют прежнее поведение
- Песочница: RestrictedPython 8.5; для ограниченных возможностей возвращается
  `error_type=RestrictedFeatureError` вместо сырого `NotImplementedError`
- nginx: заголовки безопасности на уровне `server`, кэш `/assets/` через
  `expires` (без `add_header`, чтобы не отключать наследование)
- CI: job `Security`; prod-compose берёт `ALLOWED_ORIGINS` из ENV

### Исправлено
- После перезагрузки страницы защищённые маршруты висели на Spinner:
  `loadMe()` теперь вызывается при старте приложения
- Лимит памяти песочницы на Windows больше не «декоративный»: Job Object
  реально ограничивает committed memory (KI-009)
- Промпт среднего уровня: примеры — на других данных, при просьбе «напиши
  программу» — только каркас и шаги; версия промпта intermediate = 2
  (по итогам живого прогона, KI-008)
- `GET /tasks/{id}/hints/{index}` больше не анонимный: требуется токен
  (S20-003, найдено аудитом доступа)
- Prod-Docker: backend-контейнер применяет миграции при старте
  (`docker-entrypoint.sh` → `alembic upgrade head`, отключается
  `SKIP_MIGRATIONS=true`); на чистой БД API больше не падает с
  `UndefinedTableError` (S20-006)
- `.dockerignore` для backend/frontend: venv, кэши, `node_modules`, `dist` и
  ассеты Monaco больше не попадают в контекст сборки (S20-006)
- Каталог задач больше не «протекает» между учениками: ключ кэша включает
  `user_id` и все фильтры (S19-003)

### Безопасность
- Удалён `python-jose 3.3.0` (2 critical + 1 moderate; транзитивные `ecdsa`/
  `rsa` тоже ушли), JWT переведён на **PyJWT 2.15.1** (закрыты все известные
  GHSA: 2.10.0 → 2.15.1)
- `python-multipart` 0.0.17 → **0.0.31** (GHSA-wp53-j4wj-2cfg,
  GHSA-pp6c-gr5w-3c5g, GHSA-5rvq-cxj2-64vf, GHSA-v9pg-7xvm-68hf)
- RestrictedPython 7.4 → **8.5**: GHSA-gmj9-h825-chq2 (`try/except*` type
  confusion), GHSA-ffg3-p8fm-mjx2 (shadowing guard-хуков),
  GHSA-hp3v-5vw7-fx9w (`string.Formatter` field resolution) — 3 high обхода
  песочницы закрыты; побочный эффект — `.format()`/`format_map()`/
  `string.Formatter` запрещены (KI-018), f-строки и `%` работают
- Frontend: `vitest`/`@vitest/coverage-v8` 3.2.7 → **4.1.12**
  (tinypool GHSA-5gmw-xhrv-c9v3, GHSA-85c8-ppgw-ccpr — 2 critical +
  3 moderate dev-зависимостей закрыты; `pnpm audit` — 0)
- nginx CSP без `unsafe-eval` (Monaco и worker'ы работают), HSTS,
  `frame-ancestors 'none'`; секреты в prod-compose обязательны (`:?`),
  `DEBUG=false`, БД/Redis не публикуются
- `gitleaks` 8.30.1: 0 утечек на 42 коммитах; правила под проект
  (`deepseek-api-key`, `postgres-password-in-url`, `jwt-secret-assignment`)
- Остаточные риски приняты и отслеживаются: KI-015 (starlette 0.41.3 —
  транзитивно от `fastapi 0.115.5`, неиспользуемые векторы), KI-016
  (dev-only `pytest 8.3.3`); `pip-audit` — 0 critical, CI-команда с 8
  временными `--ignore-vuln` (7 starlette + 1 pytest) даёт
  «No known vulnerabilities found, 16 ignored», exit 0

### Удалено
- `python-jose` (и транзитивные `ecdsa`, `rsa`) — заменён на PyJWT
- `@monaco-editor/react` — заменён на локальный `monaco-editor` (S19-001)

---

## [0.1.0] - 2026-10-29

Первый релиз: backend, frontend, админка, документация.

### Добавлено

**Инфраструктура**
- Структура проекта (`backend/`, `frontend/`, `docs/`), `Docker Compose`, CI GitHub Actions
- Документация: `Design.md`, `TODO.md`, `docs/RULES.md` и 15 документов в `docs/`

**Backend**
- FastAPI-приложение с health-check и структурированными логами (`structlog`)
- Модели `User`, `ChatSession`, `ChatMessage`, `CodeExecution`, `Task`, `UserTaskProgress`
- Alembic-миграции `001`–`003` (pgvector, JSONB, enum-типы)
- Репозитории с CRUD и специализированными запросами; Pydantic-схемы
- JWT-аутентификация (access 30 мин, refresh 7 дней), bcrypt, RBAC
- Эндпоинты `/auth/*`, `/users/*`, `/chat/*`, `/code/*`, `/tasks/*`, `/admin/*`
- LLM-слой: контракт `LLMProvider`, провайдеры DeepSeek и LM Studio, фабрика
- Промпты трёх уровней в файлах (`basic`, `intermediate`, `advanced`)
- Чат: сессии, история, контекст (20 сообщений), стриминг, WebSocket
- Песочница кода: AST-проверки, RestrictedPython, белый список модулей,
  изоляция процесса с убийством по таймауту, `stdin` для `input()`
- Линтер: ошибки безопасности, предупреждения стиля, подсказки, метрики
- Система задач: проверка по тест-кейсам, подсказки, прогресс, статистика
- Аналитика для админки: пользователи по ролям, DAU, задачи, попытки, активность
- Доменные ошибки `AppError` с единым HTTP-обработчиком

**Frontend**
- React 19 + Vite 6 + TypeScript strict + Tailwind 4 + ESLint/Prettier
- API-клиент с авто-refresh токена, `ApiError`, обработка ошибок Pydantic
- Zustand-сторы: `auth`, `chat`, `tasks`
- Страницы: главная, вход, регистрация, профиль, чат, песочница, задачи,
  детали задачи, админка, 404
- Чат со стримингом (WebSocket) и REST-фолбэком; блоки кода с копированием
- Monaco-редактор, панель вывода с результатом, ошибками, нарушениями, линтом
- Каталог задач с фильтрами, подсказки по одной, отчёт по тест-кейсам
- Прогресс: полоса и разбивка по сложности
- Админка: дашборд, поиск и таблица пользователей, смена ролей, список задач
- i18n ru/en, Docker-образ (node → nginx) с SPA-fallback и прокси `/api`+WS

**Тесты**
- Backend: **137** (pytest, реальный PostgreSQL, транзакционный откат)
- Frontend: **63** (Vitest + Testing Library)

### Изменено
- Внешние порты вынесены в ENV: Postgres `5434`, Redis `6381` (KI-001)
- `Settings` читает `.env` из корня проекта по абсолютному пути
- Пароли хэшируются напрямую через `bcrypt` вместо `passlib` (KI-005)
- Healthcheck возвращает `llm_provider`
- `ChatSessionCreate.level` необязателен: сессия наследует уровень профиля
- Навигация ведёт на реальные страницы; неизвестный путь → `/404`

### Исправлено
- Enum-колонки писали имена вместо значений (`STUDENT` вместо `student`) (KI-004)
- `server_default` для JSONB приводил к ошибке миграции
- Конфликт имени `metadata` с `DeclarativeBase` в модели `ChatSession`
- Дефолт `level="basic"` в запросе перебивал уровень профиля пользователя
- `app/models/__init__.py` не импортировал модели — Alembic не видел таблиц
- Lazy-relationship `task.progress` давал `MissingGreenlet` в async-сессии
- `.gitignore` с `lib/` игнорировал `frontend/src/lib/**`

### Безопасность
- Регистрация не принимает `role`: эскалация до admin/teacher закрыта (KI-011)
- bcrypt-хэширование паролей, ограничение длины 72 байтами
- JWT-токены разделены по типу (`access` / `refresh`)
- Rate limiting реализован (5/мин на login, 300/мин общий) — не подключён (KI-007)
- Песочница: запрет `os`/`sys`/`subprocess`/`open`/`eval`/`exec`, dunder-атрибутов
- Чужие ресурсы (чаты, история запусков, задачи) недоступны — 403
- Админ не может понизить или удалить сам себя

---

## Типы изменений

- `Добавлено` — новые функции
- `Изменено` — изменения в существующих функциях
- `Устарело` — функции, которые будут удалены
- `Удалено` — удалённые функции
- `Исправлено` — исправления багов
- `Безопасность` — исправления уязвимостей
