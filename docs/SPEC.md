# SPEC — спецификация проекта (источник истины по контрактам)

Документ фиксирует **контракты** системы: API, схему БД, статусы, критерии
приёмки. Архитектурные обоснования — в [../Design.md](../Design.md) и
[ARCHITECTURE.md](ARCHITECTURE.md); правила разработки — [RULES.md](RULES.md).

**Версия:** v0.2.0 «Classroom» · **Обновлено:** 2026-10-30

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

**v0.2.0 «Classroom»** добавляет: классы и назначения (S16), достижения,
дашборд и уведомления (S17), UX/тёмную тему/a11y (S18), Redis-кэш,
оптимизацию запросов и поиск по истории чата (S19), аудит зависимостей,
security-заголовки, бэкапы и релизную документацию (S20). Вне области
v0.2.0: backfill эмбеддингов для «старых» сообщений и порог релевантности
RAG (`RAG_MIN_SCORE`) — см. [reports/sprint-19/SPRINT-19.md](reports/sprint-19/SPRINT-19.md) §5.

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

Матрица «эндпоинт × роль» и IDOR-проверки — §6.4 (S20-003). Правило
неизменно: свои сущности — 200, чужие — 403, несуществующие — 404.

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
| GET | `/chat/search?q&limit` | — | `{query, mode, items[], total}` (S19-005) |

`GET /chat/levels` кэшируется в Redis на 60 с (S19-003); контракт ответа не
меняется. Поиск по истории — только свои сообщения (см. ниже).

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

**Поиск по истории чата (S19-005).**

```
GET /api/v1/chat/search?q=<строка>&limit=<1..50>

q      — обязательный, 1..200 символов (после trim пустой → 422)
limit  — опциональный; по умолчанию RAG_TOP_K (5), максимум 50

200 → {query, mode: "semantic" | "ilike",
       items: [{id, session_id, role, content, created_at, score}],
       total}
```

- Изоляция: в выдачу попадают **только сообщения из сессий текущего
  пользователя** (фильтр `chat_sessions.user_id` в репозитории); чужие — не
  попадают никогда.
- `mode="semantic"` — если `RAG_ENABLED=true`, провайдер эмбеддингов доступен
  и в БД есть векторы; `score = 1 − косинусное расстояние`.
- `mode="ilike"` — всегда доступный fallback: подстрока без учёта регистра.
  Используется при выключенном RAG, недоступном/упавшем провайдере,
  несовпадении размерности эмбеддинга и при пустой семантической выдаче.
- Ошибки: 401 — нет заголовка `Authorization` или невалидный/просроченный
  токен (Starlette 1.x `HTTPBearer`, S22-002); 422 — пустой/слишком
  длинный `q`, `limit` вне диапазона; 500 не возникает при сбое эмбеддингов
  (fail-open → ILIKE).

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

`error_type` в `ExecutionResult`: `SecurityError` (AST/рантайм-политика),
`SyntaxError`, `TimeoutError`, `SandboxError`, имя исключения Python или
`RestrictedFeatureError` — новый тип для ограничений RestrictedPython 8.5
(S20-001b). RP 8.x полностью блокирует `str.format`, `str.format_map` и
`string.Formatter` (через них обходили песочницу); вместо сырого
`NotImplementedError` возвращается подсказка: «используйте f-строки
(`f"{x}"`) или оператор `%`». F-строки и `%` работают, dunder-доступ в них
по-прежнему запрещён. Контракт выполнения остальных полей не изменился.

### 3.5 Задачи

| Метод | Путь | Тело | Ответ |
|-------|------|------|-------|
| GET | `/tasks?difficulty&category&skip&limit` | — | `TaskListItem[]` |
| GET | `/tasks/progress` | — | `ProgressSummary` |
| GET | `/tasks/stats` | — | `TaskStats` |
| GET | `/tasks/{id}` | — | `TaskDetail` |
| GET | `/tasks/{id}/hints/{index}` | — | `{index, hint, total}` |
| POST | `/tasks/{id}/submit` | `{code}` | `SubmitResponse` |
| POST | `/tasks/{id}/check` | `{code}` | `SubmitResponse` (S42-001, `practice: true`) |
| GET | `/tasks/{id}/attempts?skip&limit` | — | `AttemptList` (S42-002) |
| GET | `/tasks/{id}/attempts/{attempt_id}` | — | `AttemptDetail` (S42-002) |
| PATCH | `/tasks/{id}/draft` | `{code}` | `DraftStatus` (S42-003) |
| DELETE | `/tasks/{id}/draft` | — | `DraftStatus` (S42-003) |
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

`SubmitResponse`: `{passed, passed_count, total_count, attempts, status, results[], message, practice}`.
`AttemptItem`: `{id, task_id, passed, passed_count, total_count, created_at}`;
`AttemptDetail` — дополнительно `code` и `results[]` (разбор по кейсам);
`AttemptList`: `{items[], total}`.
`DraftStatus`: `{has_draft, updated_at}`.
`practice` — `false` для `submit`, `true` для `check`.

`POST /tasks/{id}/check` (S42-001) — пробная проверка: тест-кейсы
выполняются в песочнице, но попытка **не засчитывается** — счётчик `attempts`
и статус задачи не меняются, запись прогресса не создаётся, достижения не
начисляются. Разбор по кейсам возвращается тот же, что и у `submit`
(в ответе `attempts`/`status` — текущие значения прогресса ученика). Лимит:
не более 20 пробных проверок в минуту на пользователя, при превышении —
429 с `Retry-After: 60` (fail-open: при недоступном Redis проверка
проходит).

Пагинация каталога (S19-004) — additive: `skip` (default `0`), `limit`
(default `100`); клиенты без параметров получают прежний ответ. Кэш списка
(S19-003): ключ включает пользователя (в ответе его прогресс) и все фильтры,
TTL 60 с; инвалидация — при создании/правке/удалении/деактивации задачи,
импорте, откате версии и seed. После `POST /tasks/{id}/submit` статус в
каталоге может обновиться с задержкой ≤ TTL (инвалидация на submit не
делается).

`GET /tasks/{id}/hints/{index}` требует аутентификации (S20-003): раньше
эндпоинт был анонимным, теперь без заголовка — 401 (HTTPBearer, как и
остальные защищённые роуты), с невалидным токеном — тоже 401; поведение для
неактивной/несуществующей задачи не изменилось.

История попыток (S42-002): таблица `task_attempts` хранит каждую
**засчитанную** отправку — код, результат по каждому тест-кейсу и время.
`user_task_progress` остаётся сводкой (статус и счётчик попыток).
Пробная проверка (`POST /tasks/{id}/check`, S42-001) попытку не
засчитывает и в историю не пишется.

`GET /tasks/{id}/attempts` — постраничный список попыток **текущего
ученика** (новые сверху), `skip` (default `0`), `limit` (default `20`,
max `100`). `GET /tasks/{id}/attempts/{attempt_id}` — детальная попытка:
код и разбор по кейсам. Попытка принадлежит ученику: чужая недоступна
(404) — по идентификатору нельзя проверить существование чужой записи.
Таблица попадает под retention: `RETENTION_TASK_ATTEMPTS_DAYS` (default
90, `0` — не удалять).

Черновик решения (S42-003): колонки `draft_code` и `draft_updated_at` в
`user_task_progress` (миграция `015`). `PATCH /tasks/{id}/draft` сохраняет
черновик, `DELETE /tasks/{id}/draft` удаляет его; пустой код тоже удаляет
черновик. Лимит — 20 000 символов (как и код решения).

Черновик **не является решением**: счётчик попыток и статус задачи не
меняются, запись в историю попыток (`task_attempts`) не создаётся,
в `best_solution` не попадает. Он лежит в той же строке прогресса, поэтому
задача, у которой есть черновик, удаляется мягко (`is_active=false`) —
работа ученика сохраняется. При успешной отправке черновик очищается:
решение уже в истории. `TaskDetail` возвращает `draft_code` и
`draft_updated_at`, чтобы интерфейс восстановил черновик приоритетнее
шаблона.

### 3.6 Админка

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/admin/users` | `role?`, `search?`, `skip`, `limit` | `{total, items[]}` |
| PATCH | `/admin/users/{id}` | `{role?, level?}` | `AdminUserItem` |
| DELETE | `/admin/users/{id}` | — | `{deleted: true}` |
| GET | `/admin/tasks` | `skip`, `limit` | `{total, items[]}` |
| GET | `/admin/analytics` | — | `{users, tasks, learning, activity, llm, cache, generated_at}` |

`llm`: `{last_hour, last_24h, fallback_used, recorded_at}`; каждое окно —
`{window_hours, requests, errors, avg_latency_ms, p95_latency_ms,
avg_first_token_ms, prompt_tokens, completion_tokens, total_tokens,
by_provider}` (S12-003, метрики в памяти процесса).

`cache` (S19-003): `{enabled, hits, misses, hit_rate, sets, invalidations,
errors}`. Метрики — в памяти процесса: при нескольких воркерах каждый
показывает счётчики только своего процесса (как и `llm`).

Ограничения: 400 — понижение/удаление себя; 403 — не админ; 404 — нет пользователя.

### 3.7 Кабинет учителя

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/teacher/tasks` | `skip`, `limit` | `{total, items[]}` (включая неактивные; `total` — по всей таблице) |
| GET | `/teacher/tasks/{id}` | — | `TaskAdminDetail` |
| GET | `/teacher/students` | `search?`, `skip`, `limit` | `{total, items[]}` (агрегаты) |
| GET | `/teacher/students/{id}/progress` | — | `{student, total_tasks, completed, in_progress, completion_rate, items[]}` |

Доступ: `teacher`/`admin`; ученик получает 403. Не-ученик в
`/teacher/students/{id}` — 404.

### 3.8 Классы и назначения

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| POST | `/classrooms` | `{name}` | 201 `Classroom` (teacher/admin) |
| GET | `/classrooms` | `skip`, `limit` | `{items[]}` — свои классы (S19-004) |
| GET | `/classrooms/{id}` | — | `ClassroomDetail` (с участниками) |
| POST | `/classrooms/join` | `{join_code}` | `Classroom` |
| POST | `/classrooms/{id}/join` | `{join_code}` | `Classroom` (проверяет id) |
| DELETE | `/classrooms/{id}/members/{user_id}` | — | 204 (владелец) |
| POST | `/classrooms/{id}/assignments` | `{task_id, due_at?}` | 201 `AssignmentItem` (владелец) |
| GET | `/classrooms/{id}/assignments` | — | `{items[]}` (участник) |
| GET | `/classrooms/{id}/progress` | — | матрица + `completion_rate` (владелец) |
| GET | `/me/assignments` | — | `{items[]}` с `overdue` |

Не участник класса → 403; неверный код → 404; повторное назначение задачи → 409.

### 3.9 Вовлечение

| Метод | Путь | Параметры | Ответ |
|-------|------|-----------|-------|
| GET | `/me/achievements` | — | `{items[]}` — полученные достижения |
| GET | `/me/stats` | — | `{solved, attempts, avg_attempts, streak_days, achievements_count, chat_sessions, chat_messages}` |
| GET | `/me/notifications` | `unread_only?`, `skip`, `limit` | `{items[], unread}`; создаёт напоминания о дедлайнах |
| POST | `/me/notifications/{id}/read` | — | `NotificationItem`; чужое — 404 |

Типы уведомлений: `assignment`, `deadline`, `achievement`.

### 3.10 Служебное

`GET /health` → `{status, version, app_name, llm_provider, llm}`

`llm`: `{provider, model, configured, reachable, status, fallback}`, где
`status ∈ {ok, degraded, not_configured}` (S12-001). Проверка кэшируется на
60 секунд, ключ не раскрывается.

### 3.11. Кэш, поиск и пагинация (S19)

**Redis-кэш справочников (S19-003),** слой `app/services/cache.py`:

| Ключ | Что кэшируется | TTL |
|------|----------------|-----|
| `cache:chat:levels` | `GET /chat/levels` — статический справочник | 60 с |
| `cache:tasks:categories` | `GET /tasks/categories` | 60 с |
| `cache:tasks:list:<user>:<фильтры>` | `GET /tasks` — список с прогрессом пользователя; в ключе `user_id`, `difficulty`, `category`, `tag`, `q`, `skip`, `limit` | 60 с |

- **Инвалидация:** любая мутация задач (создание, правка, удаление/деактивация,
  импорт, откат версии, seed) удаляет namespace `cache:tasks:*` через SCAN+DEL.
  `chat:levels` статический — не инвалидируется.
- **Fail-open:** Redis недоступен → запрос обслуживается без кэша (200);
  после сбоя кэш «остывает» 10 с (`CACHE_COOLDOWN_SECONDS`), чтобы не платить
  таймаутом на каждом запросе. Ошибки логируются (`cache_get_failed` и т.п.),
  наружу не пробрасываются.
- **Метрики:** hits/misses/sets/invalidations/errors — в памяти процесса,
  отдаются в секции `cache` (см. §3.6).
- **Флаг:** `CACHE_ENABLED` (default `true`); в автотестах выключен autouse-
  фикстурой, тесты кэша используют in-memory FakeRedis.

**Пагинация (S19-004).** Новые параметры аддитивны; дефолты сохраняют прежнее
поведение:

| Эндпоинт | Параметры | Примечание |
|----------|-----------|------------|
| `GET /tasks` | `skip=0`, `limit=100` | кэшируется вместе с фильтрами |
| `GET /classrooms` | `skip=0`, `limit=100` | `members_count` — одним агрегатом |
| `GET /me/notifications` | `skip=0`, `limit=100` (1..200) | `unread` — по всей выборке |
| `GET /teacher/tasks` | `skip=0`, `limit=100` | `total` — по всей таблице, а не по странице |
| `GET /teacher/students` | `search?`, `skip=0`, `limit=100` | без изменений |
| `GET /chat/search` | `limit` (1..50, default `RAG_TOP_K`) | см. §3.3 |

**Ручные N+1-исправления (S19-004):** `GET /classrooms` (один
`JOIN … GROUP BY` вместо count на класс), `GET /classrooms/{id}/assignments`
(один `GROUP BY task_id`), `GET /classrooms/{id}` (без лишнего
`selectinload`). Индексы — миграции 0009/0010 (§4).

### 3.12. Флаги конфигурации, влияющие на контракты (S19–S20)

| Переменная | Default | Влияние на API/поведение |
|------------|---------|--------------------------|
| `CACHE_ENABLED` | `true` | выключает Redis-кэш целиком (ответы те же, без кэша) |
| `CACHE_TTL_SECONDS` | `60` | TTL записей кэша; задержка обновления каталога ≤ TTL |
| `RAG_ENABLED` | `false` | `true` включает семантический режим `/chat/search`; иначе ILIKE |
| `RAG_TOP_K` | `5` | `limit` по умолчанию у `/chat/search` |
| `RAG_EMBEDDING_DIM` | `1536` | должна совпадать с `chat_messages.embedding`; иначе → ILIKE |
| `RAG_EMBEDDING_MODEL` | `local-embedding-model` | модель на OpenAI-совместимом endpoint (LM Studio) |
| `RAG_EMBEDDING_TIMEOUT` | `5.0` с | таймаут запроса эмбеддинга |
| `LM_STUDIO_URL` | `http://127.0.0.1:8034/v1` | base URL провайдера эмбеддингов |
| `ALLOWED_ORIGINS` | `localhost:3000`/`127.0.0.1:3000` | CORS; в prod-compose задаётся ENV, не `*` |
| `EXECUTOR_*` | см. §5 | лимиты песочницы; `.format()` заблокирован независимо от настроек |

---

## 4. Схема БД (миграции 001–010)

```
users(id, email*, username*, hashed_password, role, level,
      created_at, last_active, settings JSONB)
   role ∈ {student, teacher, admin} · level ∈ {basic, intermediate, advanced}

chat_sessions(id, user_id→users, level, created_at, updated_at, metadata JSONB)
chat_messages(id, session_id→chat_sessions, role, content, code_blocks JSONB,
              metadata JSONB, embedding VECTOR(1536), created_at)
   role ∈ {user, assistant, system}
   metadata: {provider, model, prompt_version, warnings?}
   embedding — nullable: заполняется best-effort при сохранении, только если
   RAG_ENABLED=true и провайдер доступен; HNSW-индекс `vector_cosine_ops`

code_executions(id, user_id→users, code, output, error, success, execution_time,
                created_at)

tasks(id, title, description, difficulty, category, tags JSONB, test_cases JSONB,
      hints JSONB, solution_template, created_by→users, created_at, is_active)
   difficulty ∈ {easy, medium, hard} · tags — до 10, нижний регистр

task_versions(id, task_id→tasks, version, snapshot JSONB, created_by→users,
              created_at)
   UNIQUE(task_id, version) · snapshot — полное состояние задачи до правки

user_task_progress(id, user_id→users, task_id→tasks, status, attempts,
                   best_solution, completed_at, updated_at,
                   draft_code, draft_updated_at)
   status ∈ {not_started, in_progress, completed} · UNIQUE(user_id, task_id)
   draft_code — незавершённый код ученика (S42-003), не решение

task_attempts(id, user_id→users, task_id→tasks, code, passed,
               passed_count, total_count, results JSONB, created_at)
   история засчитанных отправок (S42-002) · results — разбор по кейсам

classrooms(id, name, owner_id→users, join_code*, created_at)
classroom_members(id, classroom_id→classrooms, user_id→users, role, joined_at)
   role ∈ {owner, student} · UNIQUE(classroom_id, user_id)
assignments(id, classroom_id→classrooms, task_id→tasks, due_at, created_at)
   UNIQUE(classroom_id, task_id)

achievements(code*, title, description, icon)
user_achievements(id, user_id→users, code→achievements, earned_at)
   UNIQUE(user_id, code)
notifications(id, user_id→users, type, payload JSONB, read_at, created_at)
   type ∈ {assignment, deadline, achievement}
```

Каскады: удаление пользователя → его чаты, сообщения, запуски, прогресс,
история попыток; удаление задачи → её история попыток.
Удаление задачи с прогрессом → мягкое (`is_active=false`).

Индексы: `users(email)`, `users(username)`, `chat_sessions(user_id)`,
`chat_messages(session_id)`, `code_executions(user_id)`, `tasks(difficulty)`,
`tasks(category)`, `tasks(tags)` GIN, `task_versions(task_id)`,
`user_task_progress(user_id)`, `task_attempts(user_id, task_id, created_at)`,
`task_attempts(task_id, created_at)`, `classrooms(owner_id)`,
`classroom_members(user_id)`, `assignments(classroom_id)`,
`user_achievements(user_id)`, `notifications(user_id, read_at)`.

**Миграции 0009/0010 (S19-004/005), только аддитивные:**

- `20261030_0009_query_indexes`: `tasks(is_active, created_at)`,
  `users(role, last_active)`, `notifications(user_id, created_at)`,
  `assignments(due_at)`, `chat_messages(session_id, created_at)`; дубли
  существующих индексов не создаются.
- `20261030_0010_chat_embedding_index`: HNSW-индекс
  `idx_chat_messages_embedding_hnsw` (`vector_cosine_ops`) +
  `ADD COLUMN IF NOT EXISTS embedding` (страховка; колонка есть с 001).
  В `downgrade` индекс удаляется, колонка и расширение `vector` остаются.
- Проверка: `alembic upgrade head`, `alembic check` (нет расхождений),
  цикл `downgrade base → upgrade head`, одна голова — `20261030_0010`.
- EXPLAIN-обоснование индексов — [reports/sprint-19/SPRINT-19.md](reports/sprint-19/SPRINT-19.md) §3.

---

## 5. Песочница: политика

| Параметр | Значение |
|----------|----------|
| Разрешённые модули | `math, random, datetime, collections, itertools, functools, string, re, statistics, decimal, fractions, json` |
| Запрещённые модули | `os, sys, subprocess, socket, shutil, pathlib, importlib, builtins, ctypes, multiprocessing, threading, sqlite3, http, urllib, requests, pickle, marshal` |
| Запрещённые вызовы | `open, eval, exec, compile, globals, locals, __import__` (прямой) |
| Dunder-атрибуты | запрещены |
| Таймаут | `EXECUTOR_TIMEOUT` (5 с) — **на каждый кейс**; процесс убивается |
| Память | `EXECUTOR_MEMORY_LIMIT` (128 МБ): `RLIMIT_AS` / Job Object |
| Параллельные запуски | `EXECUTOR_MAX_CONCURRENCY` (4), при перегрузке 503 |
| Пул тёплых процессов (S23) | `EXECUTOR_POOL_SIZE` (2; 0 — выключен), перезапуск после `EXECUTOR_POOL_MAX_TASKS` (50) задач и после сбоя |
| Батч тест-кейсов (S23) | все кейсы задачи — один процесс, результат по кейсам; зависший кейс → `TimeoutError`, остальные → `SandboxError` |
| Throughput submit | 5 RPS, p95 ≤ 2000 мс (`docs/reports/sprint-23/LOAD_TEST-SUBMIT.md`) |
| Режим исполнения (S24) | `EXECUTOR_MODE=native` (по умолчанию) или `container`; образ `EXECUTOR_IMAGE`. Контейнер: `--network none`, `--read-only`, `--cap-drop ALL`, `no-new-privileges`, non-root `65534`, tmpfs `/tmp`, `--memory`; при недоступном Docker — fallback на native + warning |
| Вывод | `EXECUTOR_MAX_OUTPUT` (100 000 символов), обрезка с пометкой |
| Размер кода | ≤ 20 000 символов |
| `input()` | читает подготовленный `stdin`, на исчерпании возвращает `""` |
| Форматирование строк | `str.format`/`format_map`, `string.Formatter` **запрещены** (RestrictedPython 8.5); f-строки и `%` работают → `error_type=RestrictedFeatureError` |

Реализация — RestrictedPython **8.5** (S20-001b): закрыты 3 high-обхода
песочницы (`try/except*`, shadowing guard-хуков, `string.Formatter`).
Ограничение `.format()` — осознанная плата за безопасность, зафиксировано в
KI-018; подсказка ученику возвращается в `error`.

---

## 6. Безопасность, эксплуатация и бэкапы (S20)

### 6.1. Заголовки безопасности nginx (S20-002)

Задаются на уровне `server` в `frontend/nginx.conf` (наследуются во все
`location`, где нет собственных `add_header`):

| Заголовок | Значение |
|-----------|----------|
| `Content-Security-Policy` | `default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; frame-src 'none'; form-action 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; worker-src 'self' blob:; child-src 'self' blob:; manifest-src 'self'` |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=(), browsing-topics=()` |
| `Strict-Transport-Security` | `max-age=31536000` (эффект только по HTTPS) |
| `server_tokens` | `off` |

- `script-src 'self'` — Vite собирает внешние хэшированные бандлы, inline-
  скриптов в `dist/index.html` нет; `unsafe-eval` не требуется (проверено
  Playwright с локальным Monaco).
- `style-src 'unsafe-inline'` — React/Tailwind и Monaco используют
  style-атрибуты; `worker-src blob:` — worker'ы Monaco; `connect-src 'self'` —
  `/api` и WebSocket на том же origin.
- `index.html` отдаётся с `Cache-Control: no-cache`, SPA-fallback — `try_files`.
- Проверка: `curl -I http://<host>/` → все заголовки присутствуют.

### 6.2. Секреты, CI и аудит зависимостей (S20-001/002)

- **Секреты:** `.env`/`.env.local` и `backups/` в `.gitignore`; `.gitleaks.toml`
  (встроенные правила + `deepseek-api-key`, `postgres-password-in-url`,
  `jwt-secret-assignment`; allowlist — только плейсхолдеры/тестовые значения).
  Проверка `gitleaks git . --config .gitleaks.toml --redact`: **0 утечек на 42
  коммитах**; негативный контроль подтвердил, что правила ловят фейковые
  секреты.
- **Prod-compose:** `POSTGRES_PASSWORD`/`SECRET_KEY` обязательны (`:?` — без
  них compose падает), `DEBUG=false`, порты БД/Redis наружу не публикуются,
  `ALLOWED_ORIGINS` — из ENV (не `*`).
- **CI job `Security`:** `pip-audit -r backend/requirements.txt --strict
  --desc` (с временными `--ignore-vuln` для задокументированных остатков),
  `gitleaks` по всей истории (fetch-depth 0), `pnpm audit --audit-level=high`.
  Авторитетна проверка в CI/контейнере: на машине разработки PyPI с хоста
  заблокирован (KI-017), локальный fallback — `backend/scripts/audit_python_deps.py`
  по GitHub Advisory API (лимит 60 запросов/час, `--resume`/`--offline`).
- **Dependabot:** `.github/dependabot.yml` — pip (`/backend`), npm (`/frontend`),
  github-actions; weekly, группы minor/patch.
- **Итог аудита:** frontend — `0` известных уязвимостей (`pnpm audit`);
  backend — `0 critical`; остаточные записи (`pip-audit`): **16 записей в 2
  пакетах** — `starlette 0.41.3` (транзитивно от `fastapi 0.115.5`: 7 ID;
  high — PYSEC-2026-161/248, остальные medium/low) и dev-only
  `pytest 8.3.3` (PYSEC-2026-1845). Закрыты: `python-jose` (critical,
  удалён → PyJWT 2.15.1), `ecdsa`, `python-multipart` 0.0.31,
  `RestrictedPython` 8.5 (3 high обхода песочницы), frontend vitest 4.1.12.
  Остатки — принятые риски KI-015/KI-016, неиспользуемые векторы starlette:
  файлы отдаёт nginx, `StaticFiles`/`FileResponse` в API не используются,
  тела — JSON, Host/urlencoded-векторы не задействованы. **Формулировка
  «аудит полностью чистый» некорректна** — корректно: «0 critical, high только
  в транзитивном starlette с неприменимыми векторами, риск принят и
  отслеживается».

### 6.3. Бэкап и восстановление (S20-004)

Скрипты в `scripts/` (bash; Windows — Git Bash), работают через
`docker exec <container> pg_dump` — локальный `pg_dump` не нужен.

| Скрипт | Что делает |
|--------|------------|
| `backup.sh` | `pg_dump -Fc` → gzip → `<DB>_<UTC>.dump.gz` + `.sha256`; проверка `pg_restore -l`; retention (`-r`, default 14 дней); проверяет, что контейнер запущен (иначе дамп мог бы уйти в чужую БД — KI-001) |
| `restore.sh` | восстановление в scratch-БД (по умолчанию), `--create`, `--clean`, `--verify` (счётчики таблиц/строк); guard: рабочую БД (`ai_teacher`) без `--force` не перезаписывает; запрещает `postgres`/`template0`/`template1`; требует подтверждения без `-y` |

ENV: `POSTGRES_CONTAINER`, `POSTGRES_DB`, `POSTGRES_USER`, `BACKUP_DIR`,
`BACKUP_RETENTION_DAYS`. Коды возврата: `0` — успех, `1` — ошибка, `2` —
отказ/неверные аргументы. Smoke 2026-10-30: восстановлено **14/14 таблиц**,
счётчики строк совпали, `alembic_version=010`. Подробно —
[GETTING_STARTED.md](GETTING_STARTED.md) §8 и
[DESIGN_ADMIN_AND_OPS.md](DESIGN_ADMIN_AND_OPS.md) §6/§7.

### 6.4. Матрица доступа и IDOR (S20-003)

Проверка «эндпоинт × роль» и IDOR по всем сущностям: отчёт
`docs/reports/sprint-20/ACCESS_MATRIX.md`, автотест
`backend/tests/test_access_matrix.py`, исправление: `GET /tasks/{id}/hints/{index}`
теперь требует аутентификации.

**Результат S20-003:** 35 тестов (17 функций) — все проходят; **IDOR не
найден**; одна находка F1 (LOW, hints был анонимным) исправлена. Нюанс
конвенции: отсутствие заголовка `Authorization` → **401**, невалидный/
просроченный токен → **401** (одинаково для всех защищённых маршрутов).
До S22-002 отсутствие заголовка давало 403 — Starlette 1.x выровнял поведение
по RFC 7235 (401 + `WWW-Authenticate`), клиентский код это не затрагивает.

---

## 7. Статусы и переходы

**Прогресс задачи:**

```
not_started ──submit(неверно)──► in_progress ──submit(верно)──► completed
      └──────────────────────────submit(верно)──────────────────┘
```

Задача решена ⇔ все тест-кейсы пройдены. Попытки накапливаются, лимита нет.

**Сессия чата:** создаётся с уровнем (профиля или переданным), живёт до удаления.

**Кэш (S19-003):** каталог задач и справочники живут в кэше до `TTL` (60 с);
мутация задач инвалидирует namespace сразу, а `submit` — нет (статус в
каталоге может отставать до TTL). Это осознанное поведение, а не дефект.

---

## 8. Критерии приёмки v0.1.0

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
(KI-013). `KI-007` и `KI-012` закрыты в S11; `KI-008`, `KI-009` — в S13,
`KI-013` — в S19.

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

### Дополнение v0.2.0 (спринты 19–20)

- [x] Redis-кэш справочников и каталога: hit/miss, инвалидация на CRUD/импорт/
      seed, fail-open + 10 с cooldown, секция `cache` в `/admin/analytics`
- [x] Пагинация списков (tasks/classrooms/notifications/teacher), N+1 в классах
      устранены, `GET /teacher/tasks.total` — по всей таблице
- [x] Индексы 0009/0010 (EXPLAIN-подтверждение), HNSW `vector_cosine_ops`,
      `alembic check` чист, одна голова 0010
- [x] `GET /chat/search`: только свои сообщения, `mode=semantic|ilike`,
      ILIKE-fallback при выключенном/сбойном RAG
- [x] Security-заголовки nginx (CSP без `unsafe-eval`), Monaco работает офлайн
- [x] `python-jose` удалён → PyJWT 2.15.1; `python-multipart` 0.0.31;
      frontend vitest 4.1.12 (`pnpm audit` — 0)
- [x] RestrictedPython 8.5 (3 high обхода закрыты); `.format()` заблокирован
      с понятной подсказкой (`RestrictedFeatureError`)
- [x] `gitleaks` — 0 утечек на 42 коммитах; CI job `Security`; Dependabot
- [x] `scripts/backup.sh`/`restore.sh`; smoke — 14/14 таблиц, retention/guard
- [x] `GET /tasks/{id}/hints/{index}` требует аутентификации (S20-003)
- [x] Остаточные риски задокументированы: KI-015 (starlette/fastapi),
      KI-016 (dev pytest), KI-017 (PyPI с хоста), KI-018 (`.format()`)
- [x] Автотесты: backend — **341 passed, 1 skipped** (342 collected); frontend
      80 unit + 12 e2e (**12/12 green**); ruff/mypy/typecheck/lint — 0
- [x] Документация v0.2.0: SPEC, CHANGELOG, RELEASES, KNOWN_ISSUES, RULES,
      MANUAL_TESTING_GUIDE, README; отчёты sprint-19/sprint-20
- [x] Нагрузочный профиль S19-006 зафиксирован: `health` 50 RPS p95 6.3 мс,
      каталог 20 RPS p95 25.4 мс; 5 RPS `submit` **не достигнуты** (факт
      2.5 RPS, p95 2219.7 мс при бюджете 2000 мс, knee ≈2 RPS) — ограничение
      песочницы, **KI-022**, рекомендации в `reports/sprint-19/LOAD_TEST.md` §5
- [x] Матрица доступа S20-003: **35 тестов**, IDOR не найден; находка F1
      (LOW, hints без auth) исправлена; отчёт `reports/sprint-20/ACCESS_MATRIX.md`
- [ ] Финальные проверки и тег `v0.2.0` (S20-006, за релиз-инженером)

---

## 9. Совместимость и версии

| Компонент | Версия |
|-----------|--------|
| Python | 3.12 (проверено также на 3.11) |
| FastAPI / Pydantic | 0.115 / 2.10 |
| Аутентификация | PyJWT 2.15.1, python-multipart 0.0.31 (python-jose удалён) |
| Песочница | RestrictedPython 8.5 |
| PostgreSQL + pgvector | 17 / образ `pgvector/pgvector:pg17` (pgvector 0.8.7) |
| Redis | 7 |
| Node.js / pnpm | 22 / 12 |
| React / Vite / TypeScript | 19 / 6 / 5.8 |
| Vitest / coverage | 4.1.12 |
| API | v1 (`/api/v1`), обратная совместимость внутри major |

---

## 15. Наблюдаемость и аудит (S25)

| Что | Контракт |
|-----|----------|
| Request-ID | заголовок `X-Request-ID` принимается и возвращается; если не передан — `uuid4`; значение попадает в логи (`request_id`) |
| `/metrics` | Prometheus text format, **без авторизации**, только внутренняя сеть; в nginx не публикуется. `METRICS_ENABLED=false` отключает |
| `/health/live` | 200, если процесс жив; зависимости не проверяются |
| `/health/ready` | 200, если БД и Redis доступны (LLM — только конфиг); иначе 503 со списком `checks` |
| `/api/v1/health` | обратно совместим: детальный статус LLM |
| `GET /api/v1/admin/audit` | admin; пагинация `skip`/`limit` (≤200), фильтры `action`, `entity_type`, `actor_id`; новые записи сверху |

**Аудит (таблица `audit_log`, миграция 011):** актор (`actor_id`, `actor_role`),
действие, сущность (`entity_type`, `entity_id`), сводка `payload` (без PII),
IP, время. Записываются: `user.updated`, `user.deleted`, `task.created`,
`task.updated`, `task.deleted`, `classroom.created`, `assignment.created`.
Запись best-effort: ошибка аудита не ломает действие (warning в лог).

---

## 16. Экспорт, retention и удаление аккаунта (S26)

| Что | Контракт |
|-----|----------|
| `GET /api/v1/admin/analytics/export` | admin; параметры `dataset` (`users`/`tasks`/`attempts`/`activity`), `format` (`csv`/`json`); потоковый ответ, `Content-Disposition: attachment`, `X-Export-Limit`; лимит `EXPORT_MAX_ROWS` (100 000, 0 — без лимита); каждое скачивание — `analytics.exported` в аудите |
| `GET /api/v1/classrooms/{id}/report` | владелец класса/админ; CSV (UTF-8 BOM), колонки `student_id, username, task_id, task_title, status, attempts, completed_at, due_at, overdue`; последняя строка — «ИТОГО»; ученик получает 403; пишется `classroom.report_exported` |
| Retention | `RETENTION_CHAT_MESSAGES_DAYS` (90), `RETENTION_CODE_EXECUTIONS_DAYS` (90), `RETENTION_NOTIFICATIONS_DAYS` (180), `RETENTION_AUDIT_LOG_DAYS` (365); `0` — отключено; применяется `backend/scripts/apply_retention.py` (`--dry-run`, `--only`, `--batch-size`) либо встроенным планировщиком: `RETENTION_SCHEDULER_ENABLED`, `RETENTION_SCHEDULER_AT` (UTC, `HH:MM`, по умолчанию `03:30`), `RETENTION_SCHEDULER_BATCH_SIZE` (1000); на время прогона — advisory-lock PostgreSQL (KI-025) |
| `DELETE /api/v1/auth/me` | тело `{"password": "..."}`; 204 при успехе, 400 при неверном пароле; анонимизация username/email, сброс пароля, `is_active=false`; событие `user.self_deleted`; необратимо |

Неактивный (`is_active=false`) аккаунт получает **401** на защищённых
маршрутах и не может войти (пароль сброшен).

---

## 17. RAG v2: порог релевантности и backfill (S27)

| Что | Контракт |
|-----|----------|
| `GET /api/v1/chat/search` | без изменений: `q` (1…200), `limit` (1…50, по умолчанию `RAG_TOP_K`); `mode` = `semantic` или `ilike`; поиск только по сессиям текущего пользователя |
| `RAG_MIN_SCORE` | 0…1, по умолчанию 0 (порог выключен). Семантические попадания с `score < RAG_MIN_SCORE` отбрасываются; если после фильтрации пусто — ILIKE-fallback (как и раньше) |
| Backfill | `python backend/scripts/backfill_embeddings.py [--dry-run] [--batch-size N] [--limit N] [--sleep S]` — заполняет `chat_messages.embedding` только у сообщений с `NULL`; идемпотентен; ошибки провайдера не прерывают прогон (`errors` в сводке); без настроенного провайдера — exit 2 |

`score` в ответе — косинусная близость `1 - distance` (4 знака). При
`RAG_MIN_SCORE=0` поведение совпадает с S19-005.

---

## 18. Teacher & Classroom v3 (S28)

| Что | Контракт |
|-----|----------|
| `POST /api/v1/classrooms/{id}/assignments/bulk` | teacher/admin, владелец класса; `{task_ids: [1…50], due_at?}` → `{created, skipped, unknown}`; дубликаты и уже назначенные — `skipped`, неизвестные/неактивные — `unknown`; 201 |
| `POST /api/v1/classrooms/{id}/assignments/from-template` | `{template_id, due_at?}` → тот же результат (шаблон применяется как массовое назначение) |
| `POST/GET /api/v1/teacher/assignment-templates`, `DELETE /{id}` | шаблоны учителя: `name` (1…120), `task_ids` (1…100); удалить может только владелец (403) |
| `GET /api/v1/classrooms/{id}/gradebook` | матрица `students/tasks/cells` (status, attempts, completed_at), `completion_rate`, `overdue`; только владелец/админ |
| `GET /api/v1/classrooms/{id}/gradebook/csv` | CSV-выгрузка журнала (формат как S26-002), аудит `gradebook.exported` |

**Email (S28-004).** `NOTIFICATIONS_EMAIL_ENABLED=false` по умолчанию; при
включении — SMTP (`SMTP_HOST/PORT/USER/PASSWORD/FROM`). Письмо уходит по
каждому новому назначению; ошибка SMTP не ломает запрос (warning в лог).
`NOTIFICATIONS_DEADLINE_HOURS` (72) — окно напоминаний (CLI
`scripts/notify_deadlines.py`).

---

## 19. UX, A11y & i18n (S29)

| Что | Контракт |
|-----|----------|
| Адаптивные таблицы | `Table` (`@/components/ui/Table`) + `Tr/Td/Th`: на экранах `<640px` заголовки скрыты, строки — карточки, в каждой ячейке подпись колонки (`data-label`); горизонтальный скролл не нужен |
| Локализация | Все пользовательские тексты — только в `src/i18n/locales/{ru,en}.json`; кириллица вне локалей запрещена (кроме тестов и учебных примеров в `CodePage`); паритет ключей ru/en обязателен |
| Аудит i18n | `node scripts/check-i18n.mjs` в CI (шаг Frontend) — падает при кириллице в коде или расхождении ключей |
| Контраст | Playwright + `axe-core` (`color-contrast`, WCAG AA) на ключевых страницах в светлой и тёмной теме — 0 нарушений |
| A11y/e2e | skip-link `a[href="#main"]`, мобильное меню (`aria-controls="mobile-nav"`), таблицы-карточки на 375px без переполнения |
