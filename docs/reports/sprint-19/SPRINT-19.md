# Sprint 19: Performance & Scale — Отчёт

**Период:** 2026-10-29 … 2026-10-30
**Статус:** ✅ Завершён: S19-001…S19-005, S19-007; S19-006 выполнен (qa-access) —
профиль зафиксирован, целевые 5 RPS submit **не достигнуты** (knee ≈2 RPS,
**KI-022**). Отчёты: этот файл + [LOAD_TEST.md](LOAD_TEST.md).

---

## 1. Файлы (+/-)

S19-003/004/005 (backend, этот отчёт):

```
+ backend/app/services/cache.py                       — Redis-кэш + метрики, fail-open
+ backend/app/services/rag.py                         — RAG-lite: semantic/ILIKE, best-effort эмбеддинги
+ backend/app/services/llm/embeddings.py              — провайдер эмбеддингов (LM Studio /embeddings)
+ backend/alembic/versions/20261030_0009_query_indexes.py
+ backend/alembic/versions/20261030_0010_chat_embedding_index.py
+ backend/tests/test_cache.py                         — 9 тестов
+ backend/tests/test_rag_search.py                    — 10 тестов
+ backend/tests/test_query_optimization.py            — 7 тестов
~ backend/app/config.py                              — CACHE_* (S19-003), RAG_* (S19-005)
~ backend/app/api/v1/chat.py                         — кэш /chat/levels, GET /chat/search
~ backend/app/api/v1/tasks.py                        — кэш категорий и списка задач
~ backend/app/api/v1/admin.py                        — секция cache в /admin/analytics
~ backend/app/api/v1/classrooms.py                   — N+1 fix, пагинация /classrooms
~ backend/app/api/v1/engagement.py                   — пагинация /me/notifications
~ backend/app/api/v1/teacher.py                      — пагинация /teacher/tasks
~ backend/app/api/websocket.py                       — провайдер эмбеддингов в ChatService
~ backend/app/services/task_service.py               — инвалидация кэша на CRUD/restore
~ backend/app/services/task_import.py                — инвалидация кэша на импорте
~ backend/app/services/seed_service.py               — инвалидация кэша на seed
~ backend/app/services/chat_service.py               — best-effort эмбеддинги, метод search
~ backend/app/services/classroom_service.py          — aggregate-запросы вместо N+1
~ backend/app/services/engagement_service.py         — пагинация уведомлений
~ backend/app/db/repositories/chat.py                — поиск по своим сессиям, embedding в create
~ backend/app/db/repositories/task.py                — count_tasks для пагинации
~ backend/app/models/chat.py                         — EMBEDDING_DIM, индексы session_created + HNSW
~ backend/app/models/task.py / classroom.py / engagement.py / user.py — индексы 0009
~ backend/app/schemas/admin.py                       — AnalyticsCache
~ backend/app/schemas/chat.py                        — ChatSearchItem/ChatSearchResponse
~ backend/tests/conftest.py                          — autouse-фикстура disable_cache
~ backend/tests/test_admin.py                        — контракт analytics с секцией cache
~ docs/ARCHITECTURE.md                               — §6.2 кэш, §6.3 RAG, §6.4 оптимизация
~ README.md                                          — метрики (297 тестов, head 010), фича-буллеты
~ docs/reports/sprint-19/SPRINT-19.md                — этот отчёт
```

S19-001/002 (frontend, выполнены ранее — без изменений в этом шаге):

```
+ frontend/src/lib/monacoSetup.ts
+ frontend/src/components/code-editor/MonacoEditor.tsx
+ frontend/scripts/copy-monaco.mjs, check-offline.mjs
~ frontend/src/components/code-editor/CodeEditor.tsx
~ frontend/src/App.tsx, vite.config.ts, package.json, pnpm-lock.yaml
~ .gitignore
```

S19-006 (нагрузка, qa-access):

```
+ backend/scripts/load_test.py                        — httpx+asyncio раннер, 3 сценария, JSON
+ docs/reports/sprint-19/LOAD_TEST.md                 — методика, p50/p95/p99, деградация
```

---

## 2. Покрытие

| Проверка | Было (baseline) | Стало |
|----------|-----------------|-------|
| Backend pytest | 271 passed + 1 skipped | **297 passed + 1 skipped** (+26) на шаге S19-003…005; финальный прогон v0.2.0 — **341 passed + 1 skipped** (342 collected, 200.41 с) |
| `test_cache.py` | — | 9: hit/miss/TTL, инвалидация (create/update/delete/seed), флаг, fail-open, analytics |
| `test_rag_search.py` | — | 10: ILIKE, semantic-ранжирование, изоляция сессий, 401, 422, limit, сбой эмбеддингов, фабрика |
| `test_query_optimization.py` | — | 7: индексы 0009/0010, N+1 классов/назначений, пагинация задач/уведомлений/классов/teacher |
| `test_admin.py` | 11 | 11 (контракт analytics расширен секцией `cache`) |
| Frontend unit | 71 (S19-001/002) | не менялись в этом шаге |
| Migrations | 4 | 4 (`upgrade`/`downgrade`/повторный `upgrade` + одна голова) |

---

## 3. Результаты

Команды — из `backend/`, Python `backend\venv\Scripts\python.exe`.

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Ruff | `python -m ruff check app tests` | **All checks passed** (0) |
| MyPy strict | `python -m mypy app --config-file ..\pyproject.toml` | **Success: no issues found in 76 source files** |
| Tests | `python -m pytest -q` | **297 passed, 1 skipped**, 175.70 s (на шаге S19-003…005); финальный прогон v0.2.0 — **341 passed, 1 skipped**, 200.41 s |
| Нагрузка | `python scripts/load_test.py --scenario all --duration 25` | см. §3.1 (health/tasks PASS, submit ❌ p95) |
| Migrations | `python -m alembic upgrade head` | 003 → **010** (008 → 009 → 010 применены) |
| Schema sync | `python -m alembic check` | **No new upgrade operations detected** |
| Migration cycle | `pytest tests/test_migrations.py` | 4 passed (upgrade → downgrade base → upgrade) |

### EXPLAIN ANALYZE (dev DB, после `alembic upgrade head`)

Данные dev-БД почти пустые: `tasks=6`, `users=5`, `notifications=0`,
`assignments=0`, `chat_messages=0–2`, поэтому планировщик на маленьких
таблицах выбирает Seq Scan. Ниже — реальный план и план с
`SET LOCAL enable_seqscan=off`, доказывающий, что индекс существует и
используется.

| Запрос | План по умолчанию | План с `enable_seqscan=off` |
|--------|-------------------|-----------------------------|
| Каталог: `tasks WHERE is_active ORDER BY created_at` | Seq Scan + Sort, 6 rows, 0.15 ms | **Index Scan `idx_tasks_active_created`**, `Index Cond: is_active` |
| Ученики: `users WHERE role='student' ORDER BY last_active DESC` | Seq Scan + Sort, 5 rows, 0.04 ms | **Index Scan Backward `idx_users_role_last_active`** |
| Уведомления: `WHERE user_id=… ORDER BY created_at DESC` | **Bitmap Index Scan `idx_notifications_user_created`**, 0.03 ms | то же |
| Назначения: `WHERE due_at IS NOT NULL ORDER BY due_at` | **Index Scan `idx_assignments_due_at`**, 0.02 ms | то же |
| История: `chat_messages WHERE session_id=… ORDER BY created_at` | **Bitmap Index Scan `idx_chat_messages_session_created`** | то же |
| RAG: `embedding IS NOT NULL ORDER BY embedding <=> $1 LIMIT 5` | **Index Scan `idx_chat_messages_embedding_hnsw`**, 1.9 ms | тот же HNSW-план (planning дороже из-за отключённого seqscan) |

Вывод: индексы 0009/0010 валидны и используются; на реальных объёмах
(> тысяч строк) планировщик выберет их и без подсказок.

### 3.1 Нагрузочный профиль (S19-006)

Окружение: Windows 11, AMD Ryzen Z1 Extreme (8 ядер/16 потоков), 21.8 ГБ,
Python 3.11.8, uvicorn **1 worker**, `DEBUG=false`, `RATE_LIMIT_ENABLED=false`,
`CACHE_ENABLED=true`, `LLM_PROVIDER=echo`; 25 с измерения + 1 с прогрев,
открытый цикл. Полная методика, деградация и рекомендации —
[LOAD_TEST.md](LOAD_TEST.md).

| Сценарий | Цель RPS | Факт RPS | p50, мс | p95, мс | p99, мс | Ошибки | Бюджет p95 | Вердикт |
|----------|---------:|---------:|--------:|--------:|--------:|-------:|-----------:|---------|
| health `/api/v1/health` | 50 | 50.0 | 4.1 | **6.3** | 7.4 | 0% | 300 мс | ✅ PASS |
| tasks `/api/v1/tasks` | 20 | 20.0 | 12.9 | **25.4** | 107.9 | 0% | 300 мс | ✅ PASS |
| submit `/tasks/{id}/submit` | 5 | **2.5** | 1964.3 | **2219.7** | 2285.7 | 0% | 2000 мс | ❌ FAIL |

Точка деградации `submit`: 1 RPS p95 1574 мс, 2 RPS 1674 мс, 3 RPS 2387 мс,
5 RPS 2220 мс → knee ≈2 RPS, максимум ≈2.2–2.5 submit/s. Бутылочное горлышко —
песочница (3 дочерних интерпретатора на submit × ~0.5–0.6 с при
`EXECUTOR_MAX_CONCURRENCY=4` ≈ 2.3/s), БД/HTTP не лимитируют. Целевые 5 RPS
submit не входят в DoD v0.2.0 — ограничение зарегистрировано как **KI-022**.

---

## 4. Smoke (ручной сценарий)

1. **Кэш справочников.** Поднять Redis (6381), `GET /api/v1/chat/levels`
   дважды → второй ответ приходит из кэша (`cache:chat:levels` в Redis,
   `CACHE_TTL_SECONDS=60`).
2. **Инвалидация.** `POST /api/v1/tasks` (teacher) → ключи `cache:tasks:*`
   исчезают; `GET /tasks/categories` пересчитывается и содержит новую
   категорию. То же для `PATCH`, `DELETE`, импорта и seed.
3. **Метрики кэша.** `GET /api/v1/admin/analytics` (admin) → секция
   `cache {enabled, hits, misses, hit_rate, sets, invalidations, errors}`.
4. **Fail-open.** Остановить Redis → `GET /chat/levels` и `GET /tasks`
   отвечают 200 (в логе `cache_get_failed`), API не падает.
5. **Поиск (RAG выключен, по умолчанию).** `GET /api/v1/chat/search?q=цикл` →
   `mode="ilike"`, `score=null`; чужие сообщения не видны.
6. **Поиск (RAG включён).** `RAG_ENABLED=true`, в LM Studio загружена
   embedding-модель (`RAG_EMBEDDING_MODEL`): отправить сообщение, выполнить
   `GET /chat/search?q=…` → `mode="semantic"`, элементы со `score`.
   Проверено на фейковом провайдере в тестах.
7. **Сбой эмбеддингов.** Недоступный провайдер → отправка сообщения всё равно
   201, `embedding IS NULL`; поиск отдаёт `mode="ilike"`.
8. **Изоляция.** Пользователь A ищет строку из сообщения B → `total=0`.
9. **Пагинация.** `GET /me/notifications?limit=2&skip=2`,
   `GET /teacher/tasks?limit=2`, `GET /classrooms?limit=2`,
   `GET /tasks?limit=1&skip=1` — размеры страниц и `total` корректны.
10. **Нагрузка (S19-006).** `python scripts/load_test.py --scenario all
    --duration 25` при `DEBUG=false`, `LLM_PROVIDER=echo` → `health`/`tasks`
    PASS (p95 6.3/25.4 мс), `submit` FAIL по p95 (2219.7 мс > 2000 при факте
    2.5 RPS, knee ≈2 RPS) — ожидаемое ограничение песочницы, **KI-022**.

---

## 5. Что не так

- **S19-006 выполнен (qa-access), но цель 5 RPS submit не достигнута.**
  `health`/`tasks` держат 50/20 RPS с запасом, `submit` упирается в песочницу:
  knee ≈2 RPS, факт 2.5 RPS, p95 2219.7 мс при бюджете 2000 мс. Это
  ограничение архитектуры песочницы (3 процесса на submit), а не регресс
  кэша/индексов; зарегистрировано как **KI-022**, рекомендации —
  [LOAD_TEST.md](LOAD_TEST.md) §5. Нагрузку запускать только с `DEBUG=false`:
  SQLAlchemy `echo` раздувает латентность (первый прогон с `DEBUG=true` давал
  `tasks` p99 8498 мс — артефакт логирования).
- **RAG с живой моделью не проверен** — Live LM Studio с embedding-моделью на
  машине не поднят (та же причина, что KI-008). Провайдер абстрагирован и
  покрыт фейком; путь «настроен URL + модель» кода не исполнял.
- **Нет backfill эмбеддингов** для сообщений, сохранённых до включения RAG.
  Семантический поиск видит только новые сообщения; при включении флага на
  существующей БД нужен разовый скрипт (не делали — нет задачи в S19-005).
- **Нет порога релевантности.** Semantic-поиск всегда отдаёт top-k ближайших,
  даже если они нерелевантны; при пустой семантической выдаче включается
  ILIKE. Порог (`RAG_MIN_SCORE`) можно добавить позже.
- **Кэш задач зависит от прогресса пользователя** и живёт до 60 с: после
  submit статус в каталоге может обновиться с задержкой ≤ TTL. Инвалидация
  только на мутации задач (как в задаче).
- **Метрики кэша — в памяти процесса** (как у LLM-метрик): при нескольких
  воркерах `GET /admin/analytics` показывает счётчики только своего процесса.
- **EXPLAIN снят на почти пустых таблицах** — индексы подтверждены планами
  с `enable_seqscan=off` и реальными Bitmap/Index Scan там, где данных
  хватило; полноценный load-профиль — S19-006.
- Локальная dev-БД была на ревизии 003 и обновлена до 010 этим шагом
  (`upgrade head`), что и требовалось для `alembic check`.

## 6. Новые KI

**KI-022** · Accepted · Med · performance/песочница — предел throughput
`submit` ≈2 RPS: целевые 5 RPS не достигнуты, p95 2219.7 мс > бюджета 2000 мс;
причина — 3 дочерних интерпретатора на submit при
`EXECUTOR_MAX_CONCURRENCY=4`; план — один процесс на все кейсы/пул «тёплых»
интерпретаторов, поднять concurrency, очередь с 429/503 (v0.3.0).

Ранее: **KI-013** (Monaco/CDN) закрыт в S19-001. Остальные ограничения из §5 —
осознанные рамки «RAG-lite» и fail-open-кэша, зафиксированы в
`ARCHITECTURE.md`; отдельные KI не заводились (backfill эмбеддингов и
shared-метрики кэша — кандидаты на будущее).

---

## 7. Обоснование

- **Кэш — тонкий слой `cache.py`, а не декоратор роутов.** Функции
  `cache_get_json/cache_set_json/invalidate_tasks_cache` переиспользуются в
  роутах и сервисах; метрики и fail-open-логика в одном месте. SCAN+DEL по
  namespace `cache:tasks:*` выбран вместо версионирования ключей: ключей
  мало, инвалидация редкая, а версии усложнили бы ключи и чтение.
- **Ключ списка задач включает user_id.** В ответе есть статус прохождения
  конкретного ученика — без пользователя в ключе кэш «протёк» бы между
  учениками.
- **Cooldown 10 с после сбоя Redis.** Fail-open не должен превращаться в
  2-секундный таймаут соединения на каждом запросе.
- **Best-effort эмбеддинги при сохранении, а не ленивый backfill.** Дешевле
  и проще: сообщение пишется с вектором сразу; ошибка провайдера не влияет на
  ответ (fail-open). Ленивый backfill потребовал бы фоновых задач и блокировок.
- **ILIKE — не только «флаг выключен», но и fallback при сбое/пустой выдаче.**
  Так `GET /chat/search` никогда не возвращает пустоту из-за инфраструктуры.
- **HNSW, а не ivfflat.** Ivfflat требует обучающих данных (`lists`) и на
  пустой/маленькой таблице бесполезен; HNSW (pgvector 0.8.7 в образе
  `pgvector/pgvector:pg17`) строится сразу на пустой таблице и поддерживает
  `vector_cosine_ops`. Косинус — штатная метрика для текстовых эмбеддингов.
- **Колонка `embedding` не добавляется заново.** Она есть с миграции 001;
  0010 делает `ADD COLUMN IF NOT EXISTS` как страховку и создаёт индекс.
  В downgrade индекс удаляется, колонка и расширение `vector` остаются
  (RULES §11.4).
- **Только additive-миграции.** 0009 создаёт индексы, 0010 — индекс и
  страховку колонки; ни одна миграция не меняет/не удаляет данные, `alembic
  check` зелёный, downgrade→upgrade проходит.
- **Пагинация с дефолтами = прежнее поведение.** Новые параметры additive:
  клиенты без них получают те же данные (кроме `teacher/tasks`, где `total`
  теперь честный по всей таблице, а не по странице).
- **N+1 чинили только там, где он доказан code review** (классы и
  назначения); admin/teacher-эндпоинты уже агрегировали запросы — их не
  трогали, чтобы не менять поведение без выгоды.
- **Нагрузочный раннер — httpx, а не k6/locust** (PyPI с хоста заблокирован):
  открытый цикл на `asyncio` даёт честный offered RPS и перцентили на 25 с,
  не добавляя зависимостей. Результат не «подгонялся»: сценарий `submit`
  честно помечен FAIL, ограничение — KI-022, а не спрятано. Бюджеты
  (`health/tasks` 300 мс, `submit` 2000 мс) выбраны до прогона; exit-код
  раннера = 1 при нарушении.
- **`DEBUG=false` — обязательное условие нагрузки.** SQLAlchemy `echo`
  превращает каждый запрос в запись в stdout и искажает цифры (до 8.5 с p99 на
  `tasks`) — это артефакт стенда, а не свойство API.
