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
  ├─ /api/v1/chat      — сессии, сообщения, WebSocket
  ├─ /api/v1/code      — песочница, линтер, история
  ├─ /api/v1/tasks     — каталог, submit, прогресс
  ├─ /api/v1/admin     — пользователи, задачи, аналитика
  └─ /api/v1/health
  │
  ├─ PostgreSQL 17 + pgvector   (данные, эмбеддинги сообщений)
  ├─ Redis                      (rate limiting, fail-open при недоступности)
  └─ LLM: DeepSeek API | LM Studio (локально), fallback между ними
```

## 2. Backend: слои

```
app/api/v1/*        HTTP-слой: валидация схем, коды ответов
app/services/*      бизнес-логика: ChatService, TaskService, AnalyticsService
app/services/llm/*  провайдеры LLM: база, deepseek, lm_studio, echo,
                    fallback, health, metrics, policy, prompt_builder
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

Слой 3 — изоляция процесса: код выполняется в отдельном интерпретаторе
(`subprocess`), по таймауту процесс убивается.

Слой 4 — лимиты ресурсов (S13):

| Лимит | Механизм | Настройка |
|-------|----------|-----------|
| Память, POSIX | `resource.setrlimit(RLIMIT_AS)` в дочернем процессе | `EXECUTOR_MEMORY_LIMIT` |
| Память, Windows | Job Object + `JOB_OBJECT_LIMIT_PROCESS_MEMORY` | `EXECUTOR_MEMORY_LIMIT` |
| Время | `subprocess.run(timeout=...)`, процесс убивается | `EXECUTOR_TIMEOUT` |
| Параллелизм | `threading.BoundedSemaphore`, отказ 503 | `EXECUTOR_MAX_CONCURRENCY`, `EXECUTOR_QUEUE_TIMEOUT` |
| Вывод | обрезка до JSON-сериализации | `EXECUTOR_MAX_OUTPUT` |

```
POST /code/execute {code, stdin?} → {success, output, error, error_type,
                                    violations, memory_limit_enforced,
                                    output_truncated}
POST /code/lint    {code}         → {issues[], errors, warnings, infos}
POST /code/analyze {code}         → {issues[], stats{}, summary}
GET  /code/limits                 → {timeout_seconds, memory_limit_mb,
                                    max_output_chars, max_concurrency, ...}
```

Ограничения: Monaco грузится с CDN (KI-013, только фронтенд).

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

## 7. Данные

| Таблица | Назначение |
|---------|------------|
| `users` | аккаунты, роль, уровень, настройки |
| `chat_sessions` / `chat_messages` | диалоги, `embedding` (pgvector, 1536) |
| `code_executions` | история запусков кода |
| `tasks` / `user_task_progress` | задачи и прогресс |
| `task_versions` | история правок задач |
| `alembic_version` | миграции (001 → 006) |

Миграции: `backend/alembic/versions/`. Перед коммитом —
`alembic upgrade head && alembic check`.

## 8. Конфигурация

Всё через `app/config.py` (pydantic-settings). `.env` читается по абсолютному
пути от корня проекта — при запуске из `backend/` настройки не «теряются».

Ключевые переменные: `POSTGRES_*`, `REDIS_*`, `SECRET_KEY`, `LLM_PROVIDER`,
`LLM_FALLBACK_PROVIDER`, `DEEPSEEK_API_KEY`, `EXECUTOR_TIMEOUT`,
`RATE_LIMIT_ENABLED`.

## 9. Docker

- `docker-compose.yml` — dev: публикует БД и Redis на loopback, монтирует код backend.
- `docker-compose.prod.yml` — prod: БД/Redis без публикации портов, только
  frontend наружу; nginx проксирует `/api` и WebSocket.
- `frontend/Dockerfile` — node (build) → nginx (serve + reverse proxy).

## 10. Что ещё не сделано

- Живые ответы LLM не валидировались на живой модели — KI-008 Blocked:
  нет ключа/LM Studio (инструмент прогона готов).
- Лимит памяти песочницы не enforced на Windows (KI-009).
