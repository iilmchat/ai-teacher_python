# SPEC — спецификация проекта (источник истины по контрактам)

Документ фиксирует **контракты** системы: API, схему БД, статусы, критерии
приёмки. Архитектурные обоснования — в [../Design.md](../Design.md) и
[ARCHITECTURE.md](ARCHITECTURE.md); правила разработки — [RULES.md](RULES.md).

**Версия:** v0.1.0 · **Обновлено:** 2026-10-29

---

## 1. Область и цели

Ассистент-учитель по Python для школьников 10–17 лет. Требования:

| ID | Требование |
|----|------------|
| R1 | Три уровня помощи с разной образовательной политикой |
| R2 | Чат с потоковым ответом и сохранением истории |
| R3 | Безопасное выполнение кода ученика |
| R4 | Задачи с автопроверкой и прогрессом |
| R5 | Роли: ученик, преподаватель, администратор |
| R6 | Развёртывание в Docker, офлайн-данные в PostgreSQL |

Вне области v0.1.0: мобильное приложение, восстановление пароля, оплата,
мультиарендность.

---

## 2. Роли и права

| Действие | student | teacher | admin |
|----------|:-------:|:-------:|:-----:|
| Чат, песочница | ✅ | ✅ | ✅ |
| Просмотр/решение задач | ✅ | ✅ | ✅ |
| Создание/правка задач | ❌ | ✅ | ✅ |
| Просмотр всех задач (вкл. неактивные) | ❌ | ❌ | ✅ |
| Список пользователей, смена ролей | ❌ | ❌ | ✅ |
| Аналитика | ❌ | ❌ | ✅ |

Регистрация всегда создаёт `student` (KI-011). Роль выдаёт только администратор.

---

## 3. API (v1)

Базовый путь: `/api/v1`. Аутентификация: `Authorization: Bearer <access_token>`.

### 3.1 Аутентификация

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/auth/register` | `{email, username, password}` | 201 `User` |
| POST | `/auth/login` | form: `username`, `password` | 200 `{access_token, refresh_token, token_type, user}` |
| POST | `/auth/refresh` | query `refresh_token` | 200 `{access_token, refresh_token}` |
| POST | `/auth/logout` | — | 200 `{message}` |
| GET | `/auth/me` | — | 200 `User` |
| PATCH | `/auth/me` | `{email?, username?, level?, settings?}` | 200 `User` |

Ошибки: 400 (дубликат email/username), 401 (неверные данные), 422 (валидация),
429 (лимит — после подключения KI-007; реализовано в S11-003).

### 3.2 Пользователи

| Метод | Путь | Права | Ответ |
|-------|------|-------|-------|
| GET | `/users/me` | любой | `User` |
| GET | `/users/me/level` | любой | `{level, title, description, audience, gives_ready_code}` |
| PATCH | `/users/me/level` | любой | `User` |
| GET | `/users/levels` | любой | `{levels: [...]}` |
| POST | `/users/me/activity` | любой | `{status}` |
| GET | `/users/{id}` | admin | `User` |
| PATCH | `/users/{id}/role?role=` | admin | `User` |

### 3.3 Чат

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| GET | `/chat/levels` | — | `{levels: [...]}` |
| POST | `/chat/sessions` | `{level?}` | 201 `ChatSession` |
| GET | `/chat/sessions?skip&limit` | — | `ChatSession[]` |
| GET | `/chat/sessions/{id}` | — | `ChatSessionWithMessages` |
| DELETE | `/chat/sessions/{id}` | — | 204 |
| POST | `/chat/sessions/{id}/messages` | `{content}` | 201 `{user_message, assistant_message}` |

WebSocket: `/api/v1/chat/ws/{session_id}?token=<access>`

```
client → {"type":"chat","content":"..."} | {"type":"ping"}
server → {"type":"start"} | {"type":"token","content":"…"} |
         {"type":"done","content":"полный текст","warnings":[...]} |
         {"type":"error","detail":"…"} | {"type":"pong"}
```

`ChatMessage`: `{id, session_id, role, content, code_blocks, created_at,
metadata, warnings}`.

- `metadata.prompt_version` — версия промпта уровня (S12-006);
- `metadata.provider` / `metadata.model` — фактический провайдер ответа;
- `warnings` — коды нарушений политики уровня (S12-005), например
  `basic_full_solution`; ответ при этом не блокируется.

Права: своя сессия — 200; чужая — 403; несуществующая — 404.
Недоступность LLM: 503 `{detail}` (S12-002).

### 3.4 Код

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| POST | `/code/execute` | `{code, stdin?}` | `ExecutionResult` |
| POST | `/code/lint` | `{code}` | `LintResponse` |
| POST | `/code/analyze` | `{code}` | `{issues, stats, summary}` |
| GET | `/code/history?skip&limit` | — | `ExecutionRecord[]` |
| GET | `/code/history/{id}` | — | `ExecutionRecord` (своя) |
| GET | `/code/limits` | — | `{timeout_seconds, memory_limit_mb, max_output_chars, max_concurrency, queue_timeout_seconds, max_code_length, allowed_modules}` |

`ExecutionResult`: `{success, output, error, error_type, execution_time,
violations, memory_limit_enforced, output_truncated}`.

`memory_limit_enforced=false` — ОС не дала поставить лимит памяти (тогда
действует таймаут); `output_truncated=true` — вывод обрезан по
`EXECUTOR_MAX_OUTPUT`. Перегрузка песочницы → 503.

### 3.5 Задачи

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| GET | `/tasks?difficulty&category&skip&limit` | — | `TaskListItem[]` |
| GET | `/tasks/progress` | — | `ProgressSummary` |
| GET | `/tasks/stats` | — | `TaskStats` |
| GET | `/tasks/{id}` | — | `TaskDetail` |
| GET | `/tasks/{id}/hints/{index}` | — | `{index, hint, total}` |
| POST | `/tasks/{id}/submit` | `{code}` | `SubmitResponse` |
| POST | `/tasks` | `TaskCreate` | 201 `TaskAdminDetail` (teacher/admin) |
| PATCH | `/tasks/{id}` | `TaskUpdate` | `TaskAdminDetail` (teacher/admin) |
| DELETE | `/tasks/{id}` | — | 204 (teacher/admin) |
| GET | `/tasks?tag=&q=` | — | фильтр по тегу и поиск (S14-004) |
| GET | `/tasks/categories` | — | `{categories[]}` |
| POST | `/tasks/import` | `{tasks: [...]}` | `{created, skipped, errors[]}` (teacher/admin) |
| POST | `/tasks/import/preview` | `{content}` | `{tasks, errors[]}` (teacher/admin) |
| POST | `/tasks/import/file` | multipart `file` | `{created, skipped, errors[]}` (teacher/admin) |
| GET | `/tasks/export?format=json\|yaml` | — | массив задач (teacher/admin) |
| POST | `/tasks/generate` | `{topic, difficulty, count≤5}` | `{created[], rejected[], prompt_tokens, completion_tokens}` |
| GET | `/tasks/{id}/versions` | — | `{items[]}` (teacher/admin) |
| POST | `/tasks/{id}/versions/{v}/restore` | — | `TaskAdminDetail` (teacher/admin) |

`SubmitResponse`: `{passed, passed_count, total_count, attempts, status, results[], message}`.

### 3.6 Админка

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/admin/users` | `role?`, `search?`, `skip`, `limit` | `{total, items[]}` |
| PATCH | `/admin/users/{id}` | `{role?, level?}` | `AdminUserItem` |
| DELETE | `/admin/users/{id}` | — | `{deleted: true}` |
| GET | `/admin/tasks` | `skip`, `limit` | `{total, items[]}` |
| GET | `/admin/analytics` | — | `{users, tasks, learning, activity, llm, generated_at}` |

`llm`: `{last_hour, last_24h, fallback_used, recorded_at}`; каждое окно —
`{window_hours, requests, errors, avg_latency_ms, p95_latency_ms,
avg_first_token_ms, prompt_tokens, completion_tokens, total_tokens,
by_provider}` (S12-003, метрики в памяти процесса).

Ограничения: 400 — понижение/удаление себя; 403 — не админ; 404 — нет пользователя.

### 3.7 Кабинет учителя

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/teacher/tasks` | — | `{total, items[]}` (включая неактивные) |
| GET | `/teacher/tasks/{id}` | — | `TaskAdminDetail` |
| GET | `/teacher/students` | `search?`, `skip`, `limit` | `{total, items[]}` (агрегаты) |
| GET | `/teacher/students/{id}/progress` | — | `{student, total_tasks, completed, in_progress, completion_rate, items[]}` |

Доступ: `teacher`/`admin`; ученик получает 403. Не-ученик в
`/teacher/students/{id}` — 404.

### 3.8 Классы и назначения

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| POST | `/classrooms` | `{name}` | 201 `Classroom` (teacher/admin) |
| GET | `/classrooms` | — | `{items[]}` — свои классы |
| GET | `/classrooms/{id}` | — | `ClassroomDetail` (с участниками) |
| POST | `/classrooms/join` | `{join_code}` | `Classroom` |
| POST | `/classrooms/{id}/join` | `{join_code}` | `Classroom` (проверяет id) |
| DELETE | `/classrooms/{id}/members/{user_id}` | — | 204 (владелец) |
| POST | `/classrooms/{id}/assignments` | `{task_id, due_at?}` | 201 `AssignmentItem` (владелец) |
| GET | `/classrooms/{id}/assignments` | — | `{items[]}` (участник) |
| GET | `/classrooms/{id}/progress` | — | матрица + `completion_rate` (владелец) |
| GET | `/me/assignments` | — | `{items[]}` с `overdue` |

Не участник класса → 403; неверный код → 404; повторное назначение задачи → 409.

### 3.9 Служебное

`GET /health` → `{status, version, app_name, llm_provider, llm}`

`llm`: `{provider, model, configured, reachable, status, fallback}`, где
`status ∈ {ok, degraded, not_configured}` (S12-001). Проверка кэшируется на
60 секунд, ключ не раскрывается.

---

## 4. Схема БД (миграции 001–007)

```
users(id, email*, username*, hashed_password, role, level,
      created_at, last_active, settings JSONB)
   role ∈ {student, teacher, admin} · level ∈ {basic, intermediate, advanced}

chat_sessions(id, user_id→users, level, created_at, updated_at, metadata JSONB)
chat_messages(id, session_id→chat_sessions, role, content, code_blocks JSONB,
              metadata JSONB, embedding VECTOR(1536), created_at)
   role ∈ {user, assistant, system}
   metadata: {provider, model, prompt_version, warnings?}

code_executions(id, user_id→users, code, output, error, success, execution_time,
                created_at)

tasks(id, title, description, difficulty, category, tags JSONB, test_cases JSONB,
      hints JSONB, solution_template, created_by→users, created_at, is_active)
   difficulty ∈ {easy, medium, hard} · tags — до 10, нижний регистр

task_versions(id, task_id→tasks, version, snapshot JSONB, created_by→users,
              created_at)
   UNIQUE(task_id, version) · snapshot — полное состояние задачи до правки

user_task_progress(id, user_id→users, task_id→tasks, status, attempts,
                   best_solution, completed_at, updated_at)
   status ∈ {not_started, in_progress, completed} · UNIQUE(user_id, task_id)

classrooms(id, name, owner_id→users, join_code*, created_at)
classroom_members(id, classroom_id→classrooms, user_id→users, role, joined_at)
   role ∈ {owner, student} · UNIQUE(classroom_id, user_id)
assignments(id, classroom_id→classrooms, task_id→tasks, due_at, created_at)
   UNIQUE(classroom_id, task_id)
```

Каскады: удаление пользователя → его чаты, сообщения, запуски, прогресс.
Удаление задачи с прогрессом → мягкое (`is_active=false`).

Индексы: `users(email)`, `users(username)`, `chat_sessions(user_id)`,
`chat_messages(session_id)`, `code_executions(user_id)`, `tasks(difficulty)`,
`tasks(category)`, `tasks(tags)` GIN, `task_versions(task_id)`,
`user_task_progress(user_id)`, `classrooms(owner_id)`,
`classroom_members(user_id)`, `assignments(classroom_id)`.

---

## 5. Песочница: политика

| Параметр | Значение |
|----------|----------|
| Разрешённые модули | `math, random, datetime, collections, itertools, functools, string, re, statistics, decimal, fractions, json` |
| Запрещённые модули | `os, sys, subprocess, socket, shutil, pathlib, importlib, builtins, ctypes, multiprocessing, threading, sqlite3, http, urllib, requests, pickle, marshal` |
| Запрещённые вызовы | `open, eval, exec, compile, globals, locals, __import__` (прямой) |
| Dunder-атрибуты | запрещены |
| Таймаут | `EXECUTOR_TIMEOUT` (5 с), процесс убивается |
| Память | `EXECUTOR_MEMORY_LIMIT` (128 МБ): `RLIMIT_AS` / Job Object |
| Параллельные запуски | `EXECUTOR_MAX_CONCURRENCY` (4), при перегрузке 503 |
| Вывод | `EXECUTOR_MAX_OUTPUT` (100 000 символов), обрезка с пометкой |
| Размер кода | ≤ 20 000 символов |
| `input()` | читает подготовленный `stdin`, на исчерпании возвращает `""` |

---

## 6. Статусы и переходы

**Прогресс задачи:**

```
not_started ──submit(неверно)──► in_progress ──submit(верно)──► completed
      └──────────────────────────submit(верно)──────────────────┘
```

Задача решена ⇔ все тест-кейсы пройдены. Попытки накапливаются, лимита нет.

**Сессия чата:** создаётся с уровнем (профиля или переданным), живёт до удаления.

---

## 7. Критерии приёмки v0.1.0

- [x] Регистрация/вход/обновление токена; роль всегда `student`
- [x] Все защищённые эндпоинты возвращают 401/403 без прав
- [x] Чат: стриминг и REST-ответ дают одинаковый результат
- [x] Промпт выбранного уровня уходит в модель (проверено тестом)
- [x] Песочница блокирует `os`/`open`/dunder и убивает бесконечный цикл
- [x] Задача засчитывается только при прохождении всех тестов
- [x] Чужой ресурс недоступен (403)
- [x] Админ не может понизить/удалить себя
- [x] Автотесты: backend 137, frontend 63; ruff/mypy/typecheck/lint — 0
- [x] `alembic check` без расхождений
- [x] Документация: 16 файлов в `docs/`

Не входит в приёмку (осознанно): e2e (KI-012), rate limiting в рантайме
(KI-007), живые ответы LLM (KI-008), память песочницы (KI-009), офлайн-Monaco
(KI-013). `KI-007` и `KI-012` закрыты в S11; `KI-008`, `KI-009`, `KI-013`
остаются.

### Дополнение v0.2.0 (спринты 11–14)

- [x] E2E 12/12, rate limiting (429 + `Retry-After`), тесты миграций и WS
- [x] `/health` различает `ok` / `degraded` / `not_configured`, ключ не раскрыт
- [x] Fallback провайдеров; оба недоступны → 503, а не пустой ответ
- [x] Метрики LLM (латентность, первый токен, токены, ошибки) в админке
- [x] Ответ `basic` с готовым кодом помечается `warnings`
- [x] `prompt_version` / `provider` в метаданных ответа и истории
- [x] Память песочницы ограничена на Windows и Linux (KI-009 закрыт)
- [x] Вывод обрезается, число параллельных запусков ограничено
- [x] Живой прогон LLM_EVAL, оценки 0.99 / 0.93 / 0.96 (KI-008 закрыт)
- [x] Импорт/экспорт задач JSON/YAML, seed при старте (KI-010 закрыт)
- [x] Генерация задач через LLM с проверкой эталона в песочнице
- [x] Теги/поиск и история версий задач с откатом

---

## 8. Совместимость и версии

| Компонент | Версия |
|-----------|--------|
| Python | 3.12 (проверено также на 3.11) |
| FastAPI / Pydantic | 0.115 / 2.10 |
| PostgreSQL + pgvector | 17 / образ `pgvector/pgvector:pg17` |
| Redis | 7 |
| Node.js / pnpm | 22 / 12 |
| React / Vite / TypeScript | 19 / 6 / 5.8 |
| API | v1 (`/api/v1`), обратная совместимость внутри major |
