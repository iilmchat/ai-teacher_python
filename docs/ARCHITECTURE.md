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
  ├─ Redis                      (план: rate limiting, кэш)
  └─ LLM: DeepSeek API | LM Studio (локально)
```

## 2. Backend: слои

```
app/api/v1/*        HTTP-слой: валидация схем, коды ответов
app/services/*      бизнес-логика: ChatService, TaskService, AnalyticsService
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
3. Стримит дельты от провайдера через WebSocket.
4. По завершении сохраняет ответ и извлекает ```блоки кода``` в `code_blocks`.

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

```
POST /code/execute {code, stdin?} → {success, output, error, error_type, violations}
POST /code/lint    {code}         → {issues[], errors, warnings, infos}
POST /code/analyze {code}         → {issues[], stats{}, summary}
```

Ограничения: память не ограничивается на Windows (KI-009), Monaco грузится с CDN
(KI-013, только фронтенд).

## 6. Задачи и прогресс

- `Task` — описание, сложность, категория, `test_cases` (JSONB), `hints`.
- `UserTaskProgress` — уникальная пара `(user_id, task_id)`, `attempts`,
  `status` (`not_started → in_progress → completed`), `best_solution`.
- Submit: каждый кейс выполняется в песочнице с подставленным `stdin`,
  вывод сравнивается после нормализации (`\r\n`, хвостовые пробелы).
- Прогресс считается по всем активным задачам: `completion_rate`, разбивка по
  сложности.

## 7. Данные

| Таблица | Назначение |
|---------|------------|
| `users` | аккаунты, роль, уровень, настройки |
| `chat_sessions` / `chat_messages` | диалоги, `embedding` (pgvector, 1536) |
| `code_executions` | история запусков кода |
| `tasks` / `user_task_progress` | задачи и прогресс |
| `alembic_version` | миграции (001 → 003) |

Миграции: `backend/alembic/versions/`. Перед коммитом —
`alembic upgrade head && alembic check`.

## 8. Конфигурация

Всё через `app/config.py` (pydantic-settings). `.env` читается по абсолютному
пути от корня проекта — при запуске из `backend/` настройки не «теряются».

Ключевые переменные: `POSTGRES_*`, `REDIS_*`, `SECRET_KEY`, `LLM_PROVIDER`,
`DEEPSEEK_API_KEY`, `EXECUTOR_TIMEOUT`.

## 9. Docker

- `docker-compose.yml` — dev: публикует БД и Redis на loopback, монтирует код backend.
- `docker-compose.prod.yml` — prod: БД/Redis без публикации портов, только
  frontend наружу; nginx проксирует `/api` и WebSocket.
- `frontend/Dockerfile` — node (build) → nginx (serve + reverse proxy).

## 10. Что ещё не сделано

- Rate limiting реализован, но не подключён (KI-007).
- Нет e2e-тестов и проверки в браузере против живого backend (KI-012).
- Реальные ответы LLM не валидировались на живой модели (KI-008).
- Лимит памяти песочницы не enforced на Windows (KI-009).
