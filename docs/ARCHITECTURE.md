# ARCHITECTURE — как устроен AI Teacher for Python

Документ описывает **текущее** устройство системы. Исходные проектные решения —
в [../Design.md](../Design.md); правила разработки — в [RULES.md](RULES.md).

---

## 1. Компоненты

```
Браузер
  │  React 19 (Vite, TS, Tailwind 4, Monaco)
  │  Zustand: auth / chat / tasks
  ▼
nginx (frontend-контейнер)
  │  /            → статика SPA
  │  /api/*       → backend:8000 (REST)
  │  ws upgrade   → backend:8000 (чат)
  ▼
FastAPI (backend)
  ├─ /api/v1/auth      — JWT, bcrypt
  ├─ /api/v1/users     — профиль, уровень, RBAC-эндпоинты
  ├─ /api/v1/chat      — сессии, сообщения, поиск, WebSocket
  ├─ /api/v1/code      — песочница, линтер, история
  ├─ /api/v1/tasks     — каталог, submit, прогресс
  ├─ /api/v1/admin     — пользователи, задачи, аналитика
  └─ /api/v1/health
  │
  ├─ PostgreSQL 17 + pgvector   (данные, эмбеддинги + HNSW-индекс сообщений)
  ├─ Redis                      (rate limiting, кэш справочников; fail-open)
  └─ LLM: DeepSeek API | LM Studio (локально), fallback между ними
```

## 2. Backend: слои

```
app/api/v1/*        HTTP-слой: валидация схем, коды ответов
app/services/*      бизнес-логика: ChatService, TaskService, AnalyticsService,
                    cache (Redis-кэш справочников), rag (поиск по истории)
app/services/llm/*  провайдеры LLM: база, deepseek, lm_studio, echo,
                    fallback, health, metrics, policy, prompt_builder;
                    embeddings — провайдер эмбеддингов для RAG-lite
app/db/repositories Repository-паттерн: SQLAlchemy-запросы
app/models/*        ORM-модели (SQLAlchemy 2.0, Mapped)
app/schemas/*       Pydantic v2: вход/выход API
app/core/*          безопасность, исполнитель кода, линтер, test_runner
app/errors.py       доменные исключения → HTTP через единый обработчик
```

Правила слоёв:

- сервисы **не** используют `HTTPException` — только `AppError`;
- API-слой не содержит бизнес-логики;
- репозитории не знают про HTTP и сервисы.

## 3. Поток чата (стриминг)

```
POST /api/v1/chat/sessions            → создаётся ChatSession (level из профиля)
POST /api/v1/chat/sessions/{id}/messages  → REST-ответ целиком
WS   /api/v1/chat/ws/{id}?token=...   → стриминг:
   client → {"type":"chat","content":"..."}
   server → start → token×N → done
```

1. `ChatService.stream_reply` сохраняет вопрос ученика.
2. Собирает контекст: системный промпт уровня + последние 20 сообщений (≤4000 симв.)
3. Стримит дельты от провайдера через WebSocket; fallback — только до первого
   токена, иначе ошибка (S12-002).
4. По завершении сохраняет ответ с метаданными (`provider`, `model`,
   `prompt_version`, `warnings`) и извлекает ```блоки кода``` в `code_blocks`.
5. Каждый вызов провайдера попадает в метрики (`MetricsProvider`).

Если WebSocket недоступен, фронтенд отправляет тот же вопрос через REST —
поведение идентично, но без пошагового вывода.

## 4. Уровни ассистента

| Уровень | Файл промпта | Политика |
|---------|--------------|----------|
| `basic` | `prompts/basic.txt` | наводящие вопросы, **без готового кода** |
| `intermediate` | `prompts/intermediate.txt` | причина ошибки + пример синтаксиса |
| `advanced` | `prompts/advanced.txt` | полное решение, альтернативы, стиль |

- Промпты — файлы, версионируются git, покрыты тестами на маркеры.
- Уровень хранится у пользователя (по умолчанию) и у сессии (переопределение).
- Если файла промпта нет — `resolve_level` откатывается на `basic`.

## 5. Песочница кода

Слой 1 — статический AST-анализ (`find_violations`):
запрещённые импорты (`os`, `sys`, `subprocess`, …), `open`/`eval`/`exec`,
dunder-атрибуты.

Слой 2 — RestrictedPython (`compile_restricted`) + ограниченные builtins +
собственный `__import__` с белым списком модулей.

Используется RestrictedPython **8.5** (S20-001b): закрыты 3 high-обхода
(`try/except*`, shadowing guard-хуков, `string.Formatter`). Побочный эффект —
`str.format`/`format_map`/`string.Formatter` запрещены; ошибка переводится в
`error_type=RestrictedFeatureError` с подсказкой про f-строки и `%` (KI-018).

Слой 3 — изоляция процесса: код выполняется в отдельном интерпретаторе
(`subprocess`), по таймауту процесс убивается.

Слой 4 — лимиты ресурсов (S13):

| Лимит | Механизм | Настройка |
|-------|----------|-----------|
| Память, POSIX | `resource.setrlimit(RLIMIT_AS)` в дочернем процессе | `EXECUTOR_MEMORY_LIMIT` |
| Память, Windows | Job Object + `JOB_OBJECT_LIMIT_PROCESS_MEMORY` | `EXECUTOR_MEMORY_LIMIT` |
| Время | таймаут на **кейс** в родителе, процесс убивается | `EXECUTOR_TIMEOUT` |
| Параллелизм | `threading.BoundedSemaphore`, отказ 503 | `EXECUTOR_MAX_CONCURRENCY`, `EXECUTOR_QUEUE_TIMEOUT` |
| Вывод | обрезка до JSON-сериализации | `EXECUTOR_MAX_OUTPUT` |
| Пул процессов | idle-интерпретаторы, перезапуск после N задач/сбоя | `EXECUTOR_POOL_SIZE`, `EXECUTOR_POOL_MAX_TASKS` |

Слой 5 — батч и пул (S23, KI-022):

- **Батч:** все кейсы задачи выполняет один дочерний интерпретатор
  (`_BATCH_RUNNER`). Протокол — построчный JSON: на кейс строка результата,
  в конце `{"done": true}`. Родитель держит таймаут на каждый кейс, поэтому
  зависший кейс не ждёт весь батч; процесс убивается, остальные кейсы
  помечаются `SandboxError`.
- **Пул:** до `EXECUTOR_POOL_SIZE` поднятых процессов переиспользуются между
  задачами (`runner_pool.py`); изоляция — свежие `globals`/`builtins` на каждый
  кейс, перезапуск после `EXECUTOR_POOL_MAX_TASKS` задач, после
  `TimeoutError`/`MemoryError` и при shutdown приложения.
- **Эффект:** submit 5 RPS — p95 2219 мс → **49 мс**
  (`docs/reports/sprint-23/LOAD_TEST-SUBMIT.md`).

```
POST /code/execute {code, stdin?} → {success, output, error, error_type,
                                    violations, memory_limit_enforced,
                                    output_truncated}
POST /code/lint    {code}         → {issues[], errors, warnings, infos}
POST /code/analyze {code}         → {issues[], stats{}, summary}
GET  /code/limits                 → {timeout_seconds, memory_limit_mb,
                                    max_output_chars, max_concurrency, ...}
```

Ограничение снято: Monaco работает офлайн, ассеты локальные (S19-001, KI-013
закрыт).

## 6. Задачи и прогресс

- `Task` — описание, сложность, категория, `tags`, `test_cases` (JSONB), `hints`.
- `TaskVersion` — снимок задачи перед правкой (`snapshot` JSONB), уникален по
  `(task_id, version)`; откат сохраняет текущее состояние как новую версию.
- `UserTaskProgress` — уникальная пара `(user_id, task_id)`, `attempts`,
  `status` (`not_started → in_progress → completed`), `best_solution`.
- Submit: каждый кейс выполняется в песочнице с подставленным `stdin`,
  вывод сравнивается после нормализации (`\r\n`, хвостовые пробелы).
- Прогресс считается по всем активным задачам: `completion_rate`, разбивка по
  сложности.
- Контент: импорт/экспорт JSON/YAML (`task_import`), генерация через LLM с
  прогоном эталона в песочнице (`task_generation`), seed при старте
  (`seed_service`, `SEED_ON_START`).
- Кабинет учителя (`/teacher/*`): списки задач и учеников, агрегаты прогресса,
  импорт файла; доступ teacher/admin.
- Классы (`/classrooms/*`): участники по `join_code`, назначения с дедлайнами,
  матрица «ученик × задача» и `/me/assignments`.

## 6.1 Frontend

- React 19 + Vite; все страницы — `React.lazy` (route-level code splitting).
- Entry ≤ 80 kB gzip, vendor-чанки `react`/`i18n`, Monaco — отдельный чанк.
- Monaco: AMD-ассеты `min/vs` копируются в `public/monaco/vs` (prebuild),
  `MonacoEditor` грузится lazy, worker — с собственного origin; `pnpm
  test:offline` проверяет отсутствие CDN в бандле.
- `TeacherRoute` и `AdminRoute` закрывают разделы по роли.
- Достижения, streak и уведомления: `engagement_service`; уведомления создаются
  на назначение, достижение и лениво на дедлайн ≤72 ч.
- UI-токены и тёмная тема: `index.css` (`--surface`, `--border`, `--app-fg`),
  класс `dark` на `<html>`, состояние в `store/theme.ts`, Monaco `vs`/`vs-dark`.
- Дизайн-система: `components/ui/*` (Modal, Toast, Tabs, Table, Badge,
  Skeleton); `/dev/ui` собирается только в dev (`import.meta.env.DEV`).

## 6.2 Кэш справочников (S19-003)

```
GET /chat/levels      → cache:chat:levels        (TTL 60 c)
GET /tasks/categories → cache:tasks:categories   (TTL 60 c)
GET /tasks            → cache:tasks:list:<user>:<filters> (TTL 60 c)
```

- Слой — `app/services/cache.py`; Redis-клиент берётся лениво из
  `app/db/redis.py`, как у rate limiting.
- **Ключ списка задач включает пользователя** (в ответе есть его прогресс) и
  все фильтры: `difficulty`, `category`, `tag`, `q`, `skip`, `limit`.
- **Инвалидация** — namespace `cache:tasks:*` через SCAN + DEL при создании,
  правке, удалении/деактивации, импорте, восстановлении версии и seed.
  `GET /chat/levels` статический, его инвалидация не нужна.
- **Fail-open.** Redis недоступен → запрос обслуживается без кэша; после сбоя
  кэш «остывает» 10 c, чтобы не платить таймаутом соединения на каждом
  запросе.
- **Метрики** — hits/misses/sets/errors в памяти процесса, секция `cache`
  в `GET /admin/analytics`; события `cache_hit`/`cache_miss`/`cache_set`/
  `cache_invalidated` в structlog.
- Флаг `CACHE_ENABLED` (по умолчанию `true`); в тестах выключен autouse-
  фикстурой, тесты кэша подставляют in-memory FakeRedis.

## 6.3 Поиск по истории чата (RAG-lite, S19-005)

```
GET /api/v1/chat/search?q=<текст>&limit=<1..50>
→ {query, mode: "semantic" | "ilike", items: [{id, session_id, role,
   content, created_at, score}], total}
```

- Изоляция: репозиторий `ChatMessageRepository.search_*` всегда фильтрует по
  `chat_sessions.user_id` — чужие сообщения не попадают в выдачу никогда.
- **semantic** (при `RAG_ENABLED=true` и доступном провайдере): эмбеддинг
  запроса → `ORDER BY embedding <=> $1 LIMIT k` по HNSW-индексу
  `idx_chat_messages_embedding_hnsw` (`vector_cosine_ops`); `score = 1 - distance`.
- **ilike** — fallback, доступный всегда: подстрока без учёта регистра. Он же
  используется, если провайдер не настроен/упал, размерность вектора не
  совпала или семантическая выдача пуста.
- Эмбеддинги новых сообщений (вопрос и ответ) считаются **best-effort** при
  сохранении: `ChatService.send_message`/`stream_reply` оборачивают вызов
  провайдера в try/except, ошибка не мешает ответу. `embedding` nullable.
- Провайдер — `app/services/llm/embeddings.py` (LM Studio, OpenAI-совместимый
  `/embeddings`, модель `RAG_EMBEDDING_MODEL`, таймаут
  `RAG_EMBEDDING_TIMEOUT`). Размерность — `RAG_EMBEDDING_DIM` (1536).
- В тестах провайдер подменяется фейком — сеть не используется.

## 6.4 Оптимизация запросов и пагинация (S19-004)

Найденные и устранённые N+1 (по code review ключевых экранов):

| Место | Было | Стало |
|-------|------|-------|
| `GET /classrooms` | `members_count` на каждый класс | один `JOIN … GROUP BY` + пагинация |
| `GET /classrooms/{id}/assignments` | count на каждое назначение | один `GROUP BY task_id` |
| `GET /classrooms/{id}` | лишний `selectinload(members)` | участники читаются один раз |

Пагинация (additive, дефолты сохраняют прежнее поведение):
`GET /tasks` (`skip`/`limit` были), `GET /classrooms`,
`GET /me/notifications` (`skip`, `limit`), `GET /teacher/tasks`
(`skip`, `limit`, `total` по всей таблице).

Индексы миграции **0009** (модели описаны так же, `alembic check` зелёный):
`tasks(is_active, created_at)`, `users(role, last_active)`,
`notifications(user_id, created_at)`, `assignments(due_at)`,
`chat_messages(session_id, created_at)`. Существующие индексы
(`classrooms.owner_id`, `classrooms.join_code`, `classroom_members.user_id`,
`notifications(user_id, read_at)`, `task_versions.task_id`) не дублируются.
Миграция **0010** добавляет HNSW-индекс `chat_messages.embedding`
(`ADD COLUMN IF NOT EXISTS` — страховка, колонка есть с 001).

## 7. Данные

| Таблица | Назначение |
|---------|------------|
| `users` | аккаунты, роль, уровень, настройки |
| `chat_sessions` / `chat_messages` | диалоги, `embedding` (pgvector, 1536) + HNSW |
| `code_executions` | история запусков кода |
| `tasks` / `user_task_progress` | задачи и прогресс |
| `task_versions` | история правок задач |
| `classrooms` / `classroom_members` | классы и участники |
| `assignments` | назначения задач классам |
| `achievements` / `user_achievements` | справочник и полученные достижения |
| `notifications` | in-app уведомления |
| `alembic_version` | миграции (001 → 010) |

Миграции: `backend/alembic/versions/`. Перед коммитом —
`alembic upgrade head && alembic check`.

## 8. Конфигурация

Всё через `app/config.py` (pydantic-settings). `.env` читается по абсолютному
пути от корня проекта — при запуске из `backend/` настройки не «теряются».

Ключевые переменные: `POSTGRES_*`, `REDIS_*`, `SECRET_KEY`, `ALLOWED_ORIGINS`
(CORS, CSV/JSON; в prod — из ENV), `DEBUG`, `LLM_PROVIDER`,
`LLM_FALLBACK_PROVIDER`, `DEEPSEEK_API_KEY`, `LM_STUDIO_URL`/`LM_STUDIO_MODEL`,
`EXECUTOR_*`, `RATE_LIMIT_ENABLED`, `SEED_ON_START`, `CACHE_ENABLED`,
`CACHE_TTL_SECONDS`, `RAG_ENABLED`, `RAG_TOP_K`, `RAG_EMBEDDING_DIM`,
`RAG_EMBEDDING_MODEL`, `RAG_EMBEDDING_TIMEOUT`.

Скрипты бэкапа читают своё окружение: `POSTGRES_CONTAINER`, `POSTGRES_DB`,
`POSTGRES_USER`, `BACKUP_DIR`, `BACKUP_RETENTION_DAYS` (§9.3).

## 9. Безопасность и деплой (S20)

### 9.1. Заголовки безопасности

nginx-контейнер отдаёт SPA и проксирует `/api`, WebSocket. На уровне `server`
заданы: CSP (`script-src 'self'`, `worker-src 'self' blob:`, без
`unsafe-eval`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy`, `Permissions-Policy`, HSTS; `server_tokens off`.
`index.html` — `Cache-Control: no-cache`, статика `/assets/` — `expires`.

Обоснование CSP: Vite собирает внешние хэшированные бандлы (inline-скриптов
нет), Monaco работает с локальных `/monaco/vs` (S19-001), worker'ы — `blob:`,
`style-src 'unsafe-inline'` нужен React/Tailwind/Monaco. Проверено
Playwright: Monaco грузится под CSP без `unsafe-eval`.

### 9.2. Аудит зависимостей и секреты

- **CI job `Security`:** `pip-audit` (backend), `gitleaks` по всей истории,
  `pnpm audit --audit-level=high`. С S22-002/003 `--ignore-vuln` больше нет:
  `fastapi 0.162`/`starlette 1.10` и `pytest 9.2` закрыли прежние advisory,
  job должен ловить **новые** уязвимости.
- **Локально:** PyPI с хоста заблокирован (KI-017) → офлайн-wheelhouse
  (`scripts/wheelhouse.py`: `build --docker` + `install --no-index`) или аудит
  в Docker-контейнере / `backend/scripts/audit_python_deps.py` (GitHub
  Advisory API, лимит 60/час, кэш, `--resume`, exit 2 при неполном прогоне).
- **Секреты:** `.gitleaks.toml` (встроенные + проектные правила, allowlist —
  только плейсхолдеры), `.env`/`backups/` вне git; prod-compose требует
  `POSTGRES_PASSWORD`/`SECRET_KEY` (`:?`), `DEBUG=false`, БД/Redis не
  публикуются, `ALLOWED_ORIGINS` — из ENV (не `*`).
- **Dependabot** (`.github/dependabot.yml`): pip/npm/github-actions, weekly.
- **Итог v0.2.0:** frontend — 0 уязвимостей; backend — 0 critical, остаточные
  записи — принятые риски KI-015/KI-016. Закрыты: `python-jose` (→ PyJWT
  2.15.1), `python-multipart` 0.0.31, `RestrictedPython` 8.5, frontend
  `vitest` 4.1.12.

### 9.3. Бэкапы и восстановление

`scripts/backup.sh` делает `pg_dump -Fc` через `docker exec` в контейнер
БД, сжимает gzip, пишет `.sha256`, проверяет архив `pg_restore -l`, чистит
старые по retention (14 дней по умолчанию). `scripts/restore.sh`
восстанавливает в scratch-БД (`--create`/`--clean`/`--verify`), не
перезаписывает рабочую БД без `--force`, запрещает системные БД. Подробно —
[GETTING_STARTED.md](GETTING_STARTED.md) §8 и
[DESIGN_ADMIN_AND_OPS.md](DESIGN_ADMIN_AND_OPS.md) §6/§7.

## 10. Docker

- `docker-compose.yml` — dev: публикует БД и Redis на loopback, монтирует код backend.
- `docker-compose.prod.yml` — prod: БД/Redis без публикации портов, только
  frontend наружу; nginx проксирует `/api` и WebSocket.
- `frontend/Dockerfile` — node (build) → nginx (serve + reverse proxy).

## 11. Что ещё не сделано

- **RAG-lite:** нет backfill эмбеддингов для сообщений, сохранённых до
  включения RAG, и нет порога релевантности (`RAG_MIN_SCORE`); semantic-режим
  видит только новые сообщения. Живая embedding-модель не валидировалась —
  провайдер покрыт фейком (SPRINT-19 §5).
- **Кэш:** метрики в памяти процесса (не общие между воркерами); каталог
  после `submit` обновляется с задержкой до TTL (60 с).
- **Зависимости:** `fastapi 0.162` + `starlette 1.10`, `pytest 9.2` (S22-002/003);
  контракт API зафиксирован снапшотом OpenAPI (S22-001), апгрейды проверяются
  им же. PyPI с хоста заблокирован (KI-017) → wheelhouse (`scripts/wheelhouse.py`).
- **CI:** self-hosted runner, 7 job'ов (S21-003 + perf-smoke S23-003); GitHub-hosted минуты
  заблокированы биллингом (KI-014, workflow в ручном режиме), merge-gate —
  KI-023.
