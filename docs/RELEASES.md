# RELEASES.md — Журнал спринтов

> Этот документ содержит историю всех спринтов и релизов проекта.

**Текущая версия:** v0.2.0 «Classroom» (2026-10-30)  
**Текущий спринт:** 21 (этап v0.3.0 «Ops & Scale», [TODO_V0.3.md](../TODO_V0.3.md)) —
CI & Quality Gates: CI восстановлен на self-hosted runner'е, merge-gate — KI-023

---

## Оглавление

- [Спринт 1: Project Setup](#спринт-1-project-setup)
- [Спринт 2: Backend Core](#спринт-2-backend-core)
- [Спринт 3: Authentication](#спринт-3-authentication)
- [Спринт 4: Chat Service](#спринт-4-chat-service)
- [Спринт 5: Three Levels](#спринт-5-three-levels)
- [Спринт 6: Code Execution](#спринт-6-code-execution)
- [Спринт 7: Task System](#спринт-7-task-system)
- [Спринт 8: Frontend Base](#спринт-8-frontend-base)
- [Спринт 9: Frontend Features](#спринт-9-frontend-features)
- [Спринт 10: Admin & Polish — релиз v0.1.0](#спринт-10-admin--polish--релиз-v010)
- [Спринт 10: Admin & Polish — релиз v0.1.0](#спринт-10-admin--polish--релиз-v010)
- [Этап v0.2.0 «Classroom»](#этап-v020-classroom--релиз)
- [Спринт 11: Quality Gates & E2E](#спринт-11-quality-gates--e2e)
- [Спринт 12: LLMOps](#спринт-12-llmops)
- [Спринт 13: Sandbox Hardening](#спринт-13-sandbox-hardening)
- [Спринт 14: Tasks v2](#спринт-14-tasks-v2)
- [Спринт 15: Teacher Console](#спринт-15-teacher-console)
- [Спринт 16: Classrooms & Assignments](#спринт-16-classrooms--assignments)
- [Спринт 17: Engagement](#спринт-17-engagement)
- [Спринт 18: UX, A11y & Design System](#спринт-18-ux-a11y--design-system)
- [Спринт 19: Performance & Scale](#спринт-19-performance--scale)
- [Спринт 20: Security Audit & Release](#спринт-20-security-audit--release)
- [Спринт 21: CI & Quality Gates](#спринт-21-ci--quality-gates)
- [Релиз v0.2.0 «Classroom»](#релиз-v020-classroom)
- [Шаблон отчёта по спринту](#шаблон-отчёта-по-спринту)

---

## Спринт 1: Project Setup

**Период:** 2026-10-29  
**Статус:** ✅ Завершён

### Задачи
- [x] S1-001: Создание структуры директорий
- [x] S1-002: Настройка Python окружения
- [x] S1-003: Docker Compose конфигурация
- [x] S1-004: Git и CI/CD
- [x] S1-005: Документация
- [~] S1-006: Pre-commit hooks (перенесено)

### Что сделано
- Структура проекта: `backend/`, `frontend/`, `docs/`
- FastAPI-приложение с health check
- `docker-compose.yml` (PostgreSQL, Redis, backend, frontend)
- CI GitHub Actions (lint, test, frontend, docker)
- Документация: `Design.md`, `TODO.md`, `docs/RULES.md`
- Git-репозиторий и первый коммит

### Метрики
- Файлов: 30 · Коммитов: 2 · CI: настроен

---

## Спринт 2: Backend Core

**Период:** 2026-10-29  
**Статус:** ✅ Завершён

### Задачи
- [x] S2-001: FastAPI приложение
- [x] S2-002: PostgreSQL + SQLAlchemy
- [x] S2-003: Redis подключение (конфигурация)
- [x] S2-004: Alembic миграции
- [x] S2-005: Модели данных (User, ChatSession, ChatMessage)
- [x] S2-006: Pydantic схемы
- [x] S2-007: Репозитории
- [x] S2-008: Тесты Backend Core

### Что сделано
- Модели `User`, `ChatSession`, `ChatMessage` (JSONB, pgvector, enum)
- Репозитории: `BaseRepository`, `UserRepository`, `ChatSessionRepository`,
  `ChatMessageRepository`
- Pydantic-схемы для User и Chat
- Alembic: `env.py` берёт URL из `Settings`, миграция `001` создаёт схему
- Миграции применены к рабочей БД

### Проблемы
- KI-001: порты 5432/6379 заняты чужими контейнерами → перешли на 5434/6381
- KI-003: образ без pgvector → `pgvector/pgvector:pg17`
- KI-004: enum хранил имена вместо значений → `values_callable`

### Метрики
- Файлов: 15 · Миграций: 1 · Тестов на конец спринта: 6

---

## Спринт 3: Authentication

**Период:** 2026-10-29  
**Статус:** ✅ Завершён

### Задачи
- [x] S3-001: Security модуль (JWT, bcrypt)
- [x] S3-002: Auth endpoints (register, login, refresh, logout, me, patch me)
- [x] S3-003: RBAC (`require_role`)
- [x] S3-004: Rate limiting (middleware на Redis)
- [x] S3-005: Тесты authentication

### Что сделано
- `app/core/security.py`: bcrypt-хэширование, access/refresh JWT,
  `get_current_user`, `require_role` (админ имеет доступ всегда)
- `app/api/v1/auth.py`: 6 эндпоинтов, вход по username **или** email
- `app/core/rate_limiter.py`: 5 req/min на login, 300 req/min общий лимит
- 14 тестов auth + 3 теста health — все проходят

### Проблемы
- KI-005: passlib несовместим с bcrypt 5.x → прямой bcrypt
- KI-002: `create_all` в тестах скрывает расхождения с миграциями →
  добавлен `alembic check` в CI и чек-лист

### Метрики
- Тесты: **17 passed** (`pytest -q`)
- Ruff: 0 ошибок · MyPy (strict): 0 ошибок
- Smoke: register 201 → login 200 → GET /me 200 на реальном сервере

### Следующие шаги
- Спринт 5: три уровня ассистента (детализация промптов и API уровней)

---

## Спринт 4: Chat Service

**Период:** 2026-10-29  
**Статус:** ✅ Завершён (с двумя частичными пунктами)

### Задачи
- [x] S4-001: LLM Provider Interface (base, deepseek, lm_studio, фабрика)
- [x] S4-002: Chat Service (сессии, сообщения, stream_reply)
- [x] S4-003: Prompt Management (промпты в файлах, сборка сообщений)
- [x] S4-004: Context Management (последние 20 сообщений, 4000 символов)
- [x] S4-005: Chat API (5 эндпоинтов)
- [~] S4-006: WebSocket (реализован, полный стриминг не покрыт тестом — KI-006)
- [~] S4-007: Тесты (36 новых тестов; отдельный тест stream — в KI-006)

### Что сделано
- `app/services/llm/`: контракт `LLMProvider`, провайдеры DeepSeek и LM Studio,
  фабрика `create_llm_provider` по `LLM_PROVIDER`
- `app/services/llm/prompts/`: `basic.txt`, `intermediate.txt`, `advanced.txt`
  с образовательной политикой уровня
- `app/services/llm/prompt_builder.py`: загрузка промпта, обрезка истории,
  системное сообщение
- `app/services/chat_service.py`: сессии, история, `send_message`,
  `stream_reply`, извлечение блоков кода
- `app/api/v1/chat.py`: создание/список/просмотр/удаление сессий,
  отправка сообщения
- `app/api/websocket.py`: стриминг `start/token/done/error`, ping/pong,
  JWT в query-параметре
- `app/errors.py`: доменные ошибки и единый обработчик `AppError`
- Тесты: `test_chat.py` (13), `test_prompts.py` (21), `test_websocket.py` (2)

### Проблемы
- KI-006: нет интеграционного теста полного WS-стриминга
- KI-007: rate limiting всё ещё не подключён
- Провайдеры проверены только фабрикой: реальные вызовы требуют API-ключа
  или запущенного LM Studio

### Метрики
- Тесты: **53 passed** (`pytest -q`)
- Ruff: 0 ошибок · MyPy (strict): 0 ошибок
- Smoke: health отдаёт `llm_provider`, `/chat/sessions` без токена — 403,
  OpenAPI содержит 9 путей

### Следующие шаги
- Спринт 5: уровни ассистента (API уровней, переключение, fallback)

---

## Спринт 5: Three Levels

**Период:** 2026-10-29  
**Статус:** ✅ Завершён

### Задачи
- [x] S5-001: Промпты трёх уровней (созданы в спринте 4, здесь доработаны)
- [x] S5-002: Level Management (переключение уровня пользователя)
- [x] S5-003: Level-aware generation (промпт по уровню сессии + fallback)
- [x] S5-004: Level API (`/users/me/level`, `/chat/levels`, `/users/levels`)
- [x] S5-005: Тесты уровней (14 тестов)

### Что сделано
- `app/services/levels.py`: описания уровней (`title`, `description`,
  `audience`, `gives_ready_code`), `has_prompt`, `resolve_level` (fallback)
- `app/api/v1/users.py`: профиль, `PATCH /users/me/level`,
  `GET /users/me/level`, справочник, админские `GET /users/{id}` и
  `PATCH /users/{id}/role`
- `GET /chat/levels`: справочник уровней в контексте чата
- `ChatSessionCreate.level` стал необязательным — сессия наследует уровень
  профиля (найден и исправлен баг: дефолт `"basic"` перебивал наследование)
- `ChatService` применяет `resolve_level` при создании сессии и сборке промпта

### Проблемы
- KI-008: реальные ответы LLM не проверены (нет ключа)

### Метрики
- Тесты: **67 passed**
- Ruff: 0 ошибок · MyPy (strict): 0 ошибок
- Smoke: PATCH level → advanced, новая сессия `advanced`, `/chat/levels` отдаёт 3 уровня

### Следующие шаги
- Спринт 6: безопасное выполнение Python-кода (executor, linter, code API)

---

## Спринт 6: Code Execution

**Период:** 2026-10-29  
**Статус:** ✅ Завершён (memory limit не реализован — KI-009)

### Задачи
- [x] S6-001: Sandboxed Executor (RestrictedPython + отдельный процесс)
- [x] S6-002: Safe builtins и белый список модулей
- [x] S6-003: Перехват вывода и исключений
- [x] S6-004: Модель `CodeExecution` + миграция `002`
- [x] S6-005: Code API (execute, lint, analyze, history, limits)
- [x] S6-006: AST-линтер без внешних зависимостей
- [x] S6-007: Тесты (34 новых)

### Что сделано
- `app/core/executor.py`: статический анализ AST, `compile_restricted`,
  безопасные builtins, свой `__import__`, `_inplacevar_`, `PrintCollector`;
  выполнение в отдельном интерпретаторе с убийством по таймауту
- `app/core/linter.py`: ошибки безопасности (S001–S003), предупреждения
  (bare except, `== None`, длинная строка), подсказки (docstring) и метрики кода
- `app/models/code.py` + миграция `002` (`code_executions`) + репозиторий
- `app/api/v1/code.py`: `POST /code/execute`, `/code/lint`, `/code/analyze`,
  `GET /code/history`, `/code/history/{id}`, `/code/limits`
- Тесты: `test_executor.py` (12), `test_linter.py` (13), `test_code_api.py` (9)

### Проблемы
- KI-009: лимит памяти не применяется на Windows
- KI-008: реальные вызовы LLM всё ещё не проверены

### Метрики
- Тесты: **101 passed**
- Ruff: 0 ошибок · MyPy (strict): 0 ошибок
- Smoke: `sum(range(5))` → `10`; `import os` → `SecurityError`;
  линтер ловит `x == None`

### Следующие шаги
- Спринт 7: система задач и прогресс обучения

---

## Спринт 7: Task System

**Период:** 2026-10-29  
**Статус:** ✅ Завершён

### Задачи
- [x] S7-001: Модели `Task`, `UserTaskProgress` + миграция `003` + seed
- [x] S7-002: Схемы задач и валидация тест-кейсов
- [x] S7-003: `TaskService` (проверка решения, прогресс)
- [x] S7-004: `test_runner` (stdin → `input()`, нормализация вывода)
- [x] S7-005: Task API (каталог, карточка, подсказки, submit, CRUD)
- [x] S7-006: Прогресс и статистика (`/tasks/progress`, `/tasks/stats`)
- [x] S7-007: Тесты (25 новых)

### Что сделано
- Песочница научилась подавать `stdin` в `input()` (по строке на вызов)
- `app/core/test_runner.py`: прогон кейсов, сравнение без хвостовых пробелов
  и `\r\n`, лимит 20 кейсов за прогон, сбор нарушений песочницы
- `TaskService`: каталог с фильтрами, подсказки по индексу, проверка решения,
  накопление попыток, статусы `not_started → in_progress → completed`
- Мягкое удаление задачи, если по ней есть прогресс
- `seed_tasks.py`: 6 задач (ввод-вывод, условия, циклы, строки)
- **Исправлена критичная уязвимость** (KI-011): регистрация больше не принимает
  роль — иначе любой мог стать админом
- 25 новых тестов: `test_tasks.py` (14), `test_runner.py` (11)

### Проблемы
- KI-010: задачи наполняются скриптом вручную
- Урок: lazy-relationship `task.progress` в async-сессии даёт `MissingGreenlet` —
  заменено на явный запрос `exists_for_task`

### Метрики
- Тесты: **126 passed**
- Ruff: 0 ошибок · MyPy (strict): 0 ошибок · `alembic check` чист
- Smoke: 6 задач в каталоге; верное решение → 3/3, `completed`;
  неверное → 1/3; прогресс `completed=1, rate=16.7%`

### Следующие шаги
- Спринт 8: frontend (React 19 + Vite + TypeScript)

---

## Спринт 8: Frontend Base

**Период:** 2026-10-29  
**Статус:** ✅ Завершён

### Задачи
- [x] S8-001: React 19 + Vite + TypeScript strict + Tailwind 4 + ESLint/Prettier
- [x] S8-002: Структура `src/`, алиасы `@/*`, типы API
- [x] S8-003: Routing (react-router 7), layout, защищённые маршруты
- [x] S8-004: API-клиент с Bearer-токеном, авто-refresh и `ApiError`
- [x] S8-005: Zustand-стор аутентификации + localStorage
- [x] S8-006: Страницы входа и регистрации (регистрация → авто-вход)
- [x] S8-007: UI-компоненты (Button, Input, Card, Alert, Spinner)
- [x] S8-008: i18n (ru/en)
- [x] S8-009: Vitest + Testing Library (20 тестов)
- [x] S8-010: Dockerfile (node → nginx) + nginx.conf (SPA, /api, WebSocket)

### Что сделано
- Каркас `frontend/`: Vite, TypeScript project references, Tailwind 4 через плагин
- `lib/api.ts`: типизированные запросы, склейка ошибок Pydantic, авто-refresh
  по 401 с однократным повтором, событие `auth:unauthorized`
- `store/auth.ts`: вход, регистрация, выход, смена уровня, кэш профиля
- `AppLayout` с навигацией; `ProtectedRoute` редиректит на `/login` с возвратом
- Локализация ru/en, выбор языка сохраняется
- Docker-образ фронтенда с nginx: SPA-fallback, прокси `/api` и WebSocket

### Проблемы
- KI-012: нет e2e-тестов и проверки с живым backend
- Сторы чата и задач появятся в спринте 9 вместе со страницами

### Метрики
- Тесты: **20 passed** (`pnpm test`)
- `pnpm typecheck`: 0 ошибок · `pnpm lint`: 0 ошибок
- `pnpm build`: 105.49 kB gzip JS (лимит 200 kB)
- Smoke: `vite preview` отдаёт 200, SPA-fallback `/login` → 200

### Следующие шаги
- Спринт 9: чат со стримингом, редактор кода, задачи

---

## Спринт 9: Frontend Features

**Период:** 2026-10-29  
**Статус:** ✅ Завершён

### Задачи
- [x] S9-001: Chat UI (сессии, сообщения, блоки кода, ввод)
- [x] S9-002: WebSocket-стриминг + REST-фолбэк
- [x] S9-003: Выбор уровня при создании сессии
- [x] S9-004: Monaco-редактор
- [x] S9-005: Панель вывода (результат, ошибки, нарушения, линт)
- [x] S9-006: Список задач с фильтрами
- [x] S9-007: Карточка задачи, подсказки, проверка решения, результаты по кейсам
- [x] S9-008: Полоса прогресса и разбивка по сложности
- [x] S9-009: Профиль (уровень, роль)
- [x] S9-010: Тесты (40 новых)

### Что сделано
- `lib/chatSocket.ts`: протокол `start/token/done/error`, JWT в query, ping
- `hooks/useChatSession.ts`: стриминг в стор, автоматический REST-фолбэк,
  индикатор `live/rest`
- `store/chat.ts`: сессии, оптимистичные сообщения, сборка ответа из токенов
- `components/chat/*`: MessageList, MessageInput (Enter/Shift+Enter), CodeBlock
  с копированием, RichText (разбор ``` блоков), LevelSelector
- `store/tasks.ts`: каталог с фильтрами, детали, submit, прогресс
- Страницы: `/chat`, `/code`, `/tasks`, `/tasks/:id`, `/profile`
- 40 новых тестов: chat store (11), tasks store (8), компоненты чата (13),
  редактор и панель вывода (8)

### Проблемы
- KI-013: Monaco подгружается с CDN (офлайн-режим не работает)
- Авто-reconnect WebSocket не реализован: при обрыве следующий запрос идёт в REST

### Метрики
- Тесты: **60 passed** (`pnpm test`)
- `pnpm typecheck`: 0 · `pnpm lint`: 0 (0 warnings)
- `pnpm build`: **117.31 kB gzip** (лимит 200 kB)
- Smoke: `/`, `/chat`, `/code`, `/tasks`, `/tasks/:id`, `/nope` → 200 (SPA)

### Следующие шаги
- Спринт 10: админка, аналитика, документация, релиз

---

## Спринт 10: Admin & Polish — релиз v0.1.0

**Период:** 2026-10-29  
**Статус:** ✅ Завершён

### Задачи
- [x] S10-001: Admin Dashboard (сводка, пользователи, задачи)
- [x] S10-002: Управление пользователями (поиск, роли)
- [~] S10-003: Задачи в админке (просмотр; CRUD — через teacher-эндпоинты)
- [x] S10-004: Admin API (users, tasks, analytics)
- [x] S10-005: Analytics Service
- [x] S10-006: Документация (9 новых документов + обновления)
- [x] S10-007: Production docker-compose
- [~] S10-008: Производительность (бандл 119 kB, индексы; splitting отложен)
- [~] S10-009: Финальные проверки (без Playwright — KI-012)
- [x] S10-010: Релиз v0.1.0

### Что сделано
- `app/services/analytics_service.py`: пользователи по ролям, активность 24ч/7д,
  задачи по сложности, попытки/завершения, активность чата и песочницы
- `app/api/v1/admin.py`: `GET/PATCH/DELETE /admin/users`, `GET /admin/tasks`,
  `GET /admin/analytics`; защита от понижения/удаления себя
- Frontend `/admin`: дашборд, поиск и таблица пользователей со сменой роли,
  список задач; `AdminRoute` закрывает доступ не-админам
- Документация: `docs/README.md`, `GETTING_STARTED.md`, `USER_GUIDE.md`,
  `ARCHITECTURE.md`, `MANUAL_TESTING_GUIDE.md`, `ASSISTANT_LEVELS.md`,
  `PROMPT_CURRENT.md`, `LLM_EVAL.md`, `DESIGN_ADMIN_AND_OPS.md`
- `docker-compose.prod.yml`: БД/Redis без публикации портов, healthchecks
- CI: pnpm 12, `--allow-build=esbuild`, шаги lint/test для фронтенда
- 11 новых тестов админки (всего backend 137)

### Проблемы
- KI-012: нет e2e и проверки с живым backend
- KI-013: Monaco с CDN (офлайн)
- Блокировка пользователей не реализована (нет поля `is_active`)
- Экспорт аналитики и графики — в планах

### Метрики релиза
- Backend: **137 passed**, ruff 0, mypy strict 0, `alembic check` чист
- Frontend: **63 passed**, typecheck 0, lint 0, build **119 kB gzip**
- Документация: 15 файлов в `docs/` + README, Design, TODO
- Тег: `v0.1.0`

### Следующие шаги (v0.2)
- E2E-тесты (Playwright) и прогон в CI против compose-стека (KI-012)
- Подключить rate limiting (KI-007)
- Локальный Monaco bundle (KI-013)
- Живая валидация ответов LLM по методике LLM_EVAL (KI-008)
- Лимит памяти песочницы (KI-009)

---

## Этап v0.2.0 «Classroom» — релиз

**План:** [../TODO_V0.2.md](../TODO_V0.2.md) — спринты 11–20, ~24 дня.

| Спринт | Тема | Закрывает | Статус |
|--------|------|-----------|--------|
| 11 | Quality Gates & E2E | KI-001, KI-002, KI-006, KI-007, KI-012 | ✅ |
| 12 | LLMOps | KI-008 (закрыт в 13) | ✅ |
| 13 | Sandbox Hardening | KI-009 | ✅ |
| 14 | Tasks v2 | KI-010 | ✅ |
| 15 | Teacher Console | — | ✅ |
| 16 | Classrooms & Assignments | — | ✅ |
| 17 | Engagement | — | ✅ |
| 18 | UX, A11y & Design System | — | ✅ |
| 19 | Performance & Scale | KI-013 | ✅ |
| 20 | Security Audit & Release | KI-015…KI-018 (принято/закрыто) | ✅ |

Порядок обязателен: спринты 11–13 закрывают технический долг, только затем
добавляется функциональность (14–18) и оптимизации (19–20).

---

## Спринт 11: Quality Gates & E2E

**Период:** 2026-10-29  
**Статус:** ✅ Завершён

### Задачи
- [x] S11-001: E2E-каркас Playwright
- [x] S11-002: E2E-сценарии (12 тестов)
- [x] S11-003: Rate limiting подключён
- [x] S11-004: Интеграционный тест WS-стриминга (KI-006)
- [x] S11-005: Автотест миграций (KI-002)
- [x] S11-006: Покрытие и пороги
- [x] S11-007: Проверка портов (KI-001)
- [~] S11-008: Ускорение тестов (маркеры; xdist не понадобился)
- [x] S11-009: Документация

### Что сделано
- **E2E:** Playwright, отдельный backend на БД `ai_teacher_e2e` с провайдером
  `echo`, Vite на 3100 с проксированием; 12 сценариев (auth, чат, песочница,
  задачи, запрет админки); job `e2e` в CI
- **Rate limiting:** `app/db/redis.py`, middleware в `main.py`, fail-open,
  флаг `RATE_LIMIT_ENABLED`, 429 + `Retry-After`; 10 тестов на фейке Redis
- **WS-стриминг:** протокол вынесен в `serve_chat_socket`, эндпоинт на
  `Depends`; 5 тестов полного цикла и ошибок
- **Миграции:** 4 теста (upgrade на пустую БД, сверка колонок, downgrade→upgrade,
  одна голова)
- **Порты:** `scripts/check_ports.py` (БД, «свои» таблицы, Redis, `--docker`)
- **Покрытие:** backend 81% (порог 70), frontend 74/78/84% (пороги 70/60/70)
- **Провайдер `echo`:** детерминированные ответы по уровню для e2e и демо
- **Найден и исправлен баг:** после F5 защищённые страницы висели на Spinner
  (`loadMe()` не вызывался) — обнаружено e2e

### Проблемы
- В e2e используется textarea вместо Monaco (`VITE_E2E=1`) — осознанно, чтобы
  не зависеть от CDN (KI-013 остаётся для продакшена)
- Смена роли админом через UI не покрыта (нет админа в e2e; спринт 15)

### Метрики
- Backend: **156 passed** (было 137), ~59 с
- Frontend: 63 unit + **12 e2e**
- Покрытие: backend 81%, frontend 74% строк
- Ruff / MyPy: 0 / 0; TypeScript / ESLint: 0 / 0
- Закрыто KI: 5 (KI-001, KI-002, KI-006, KI-007, KI-012)

### Следующие шаги
- Спринт 12: LLMOps (healthcheck провайдера, fallback, метрики, прогон LLM_EVAL)

---

## Спринт 12: LLMOps

**Период:** 2026-10-29  
**Статус:** ⚠️ Частично (S12-004 — KI-008 Blocked: нет ключа; KI-014 — CI не стартовал)

### Задачи
- [x] S12-001: Healthcheck провайдера
- [x] S12-002: Fallback провайдеров
- [x] S12-003: Метрики LLM
- [~] S12-004: Прогон LLM_EVAL (инструмент готов; живой прогон — KI-008)
- [x] S12-005: Детектор «готового решения»
- [x] S12-006: Версия промптов в ответе
- [x] S12-007: Документация LLMOps

### Что сделано
- **Health:** `/health` → `llm{provider, model, configured, reachable, status, fallback}`;
  ping `models.list` с кэшем 60 с; без ключа — `not_configured`, а не `ok`;
  9 тестов
- **Fallback:** `LLM_FALLBACK_PROVIDER`; один повтор, лог `llm_fallback_used`;
  оба упали → 503 через обработчик `LLMUnavailableError`; fallback в стриме
  только до первого токена; 7 тестов
- **Метрики:** `MetricsProvider` — латентность, первый токен, токены, статус;
  агрегаты за час/сутки в памяти; секция `llm` в `/admin/analytics`;
  карточка в админке; 6 тестов
- **Политика уровня:** детектор готового кода/программы/фраз для `basic`;
  `warnings` в REST и WS, лог `level_policy_warning`; 8 тестов
- **Версии промптов:** `prompts/versions.json`, `chat_messages.metadata`
  (миграция 004), `provider/model/prompt_version/warnings` в истории; 5 тестов
- **LLM_EVAL:** `eval_runner` + `scripts/run_llm_eval.py` (Q1–Q5 × 3 уровня,
  `SUMMARY.md`, `results.json`), smoke на `echo`; 4 теста
- **Документация:** PROMPT_CURRENT, LLM_EVAL, DESIGN_ADMIN_AND_OPS, SPEC,
  RULES (ловушки LLM), MANUAL_TESTING_GUIDE

### Что не сделано
- Живой прогон LLM_EVAL и ручная оценка по рубрике — нет `DEEPSEEK_API_KEY`,
  LM Studio не запущен → KI-008 остаётся Blocked, сужен до «нужен ключ»
  (закрыт в спринте 13 после появления ключа и LM Studio)

### Метрики
- Backend: **200 passed** (было 156), ruff 0, mypy strict 0
- Frontend: **65 passed** (было 63), typecheck 0, lint 0, build 119.88 kB gzip
- Покрытие: backend 83% (порог 70)
- Новые тесты: 44 backend + 2 frontend
- KI: KI-008 переведён в Blocked (причина и процедура закрытия описаны);
  KI-014 — CI не стартовал из-за лимита GitHub Actions

### Проблемы
- Healthcheck и метрики требуют сети — в тестах провайдер всегда подменяется
- Параллельный запуск двух pytest-процессов ломает общую тестовую БД
  (`ai_teacher_test` пересоздаётся) — запускать прогоны последовательно
- CI не стартовал (KI-014): GitHub Actions падает за 2 с из-за лимита/платежа
  аккаунта; PR открыт, локальные проверки зелёные

### Следующие шаги
- Спринт 13: Sandbox Hardening (лимит памяти, KI-009)

---

## Спринт 13: Sandbox Hardening

**Период:** 2026-10-29  
**Статус:** ✅ Завершён (S13-006 — опционально, отложен)

### Задачи
- [x] S13-001: Лимит памяти — Linux/Docker (`RLIMIT_AS`)
- [x] S13-002: Лимит памяти — Windows (Job Object)
- [x] S13-003: Ограничение одновременных запусков (503 при перегрузке)
- [x] S13-004: Тесты на запрет сети и файловой системы (14 кейсов)
- [x] S13-005: Ограничение вывода (`EXECUTOR_MAX_OUTPUT`)
- [~] S13-006: Раннер-контейнер — не требуется, отложен
- [x] S13-007: Документация и закрытие KI-009

### Что сделано
- **Память:** `app/core/sandbox_limits.py` ставит лимит в дочернем процессе:
  `resource.setrlimit(RLIMIT_AS)` на POSIX, Job Object с
  `JOB_OBJECT_LIMIT_PROCESS_MEMORY` на Windows (ctypes, без новых зависимостей).
  `EXECUTOR_MEMORY_LIMIT` подхватывается; `memory_limit_enforced` в результате.
  Проверено: Windows — `MemoryError`, Linux-контейнер — `MemoryError`, API жив.
- **Перегрузка:** общий `threading.BoundedSemaphore`, `EXECUTOR_MAX_CONCURRENCY=4`,
  ожидание `EXECUTOR_QUEUE_TIMEOUT`, отказ 503 (`ServiceUnavailableError`).
- **Атаки:** 14 табличных кейсов — сеть, файлы, `__builtins__`, `getattr`,
  dunder, `eval`/`exec`; обходы не дают доступа.
- **Вывод:** обрезка по `EXECUTOR_MAX_OUTPUT=100000`, пометка
  `output_truncated`, суффикс «вывод обрезан».
- **API:** `/code/limits` отдаёт memory/output/concurrency/queue;
  ответ выполнения — `memory_limit_enforced`, `output_truncated`.
- **Документация:** ARCHITECTURE, DESIGN_ADMIN_AND_OPS, RULES §11.8, SPEC,
  MANUAL_TESTING_GUIDE; KI-009 → Resolved.
- **LLM_EVAL (живой):** DeepSeek, 15 ответов, баллы 0.99 / 0.93 / 0.96;
  `intermediate/Q2` исправлен промптом v2; LM Studio `qwen/qwen3-4b-2507`
  проверен как fallback; KI-008 → Resolved.

### Что не сделано
- S13-006 (раннер-контейнер) — опционально: нативные лимиты работают на обеих
  платформах; кандидат на спринт 20 (security audit).

### Метрики
- Backend: **227 passed** (+1 skip на Windows), было 200; ruff 0, mypy strict 0
- Покрытие: backend 84%
- Новые тесты: 27 backend
- Frontend: 65 unit, typecheck/lint/build — без изменений
- Закрыто KI: **KI-009**, **KI-008**

### Проблемы
- Лимит памяти ставится только в дочернем процессе: прямой вызов
  `_run_restricted` в тестах его не применяет (иначе pytest ограничивается).
- Windows Job Object не назначается, если процесс уже в несовместимом job —
  тогда `memory_limit_enforced=false` и работает только таймаут.
- CI не стартовал (KI-014, биллинг GitHub) — локальные проверки зелёные.

### Следующие шаги
- Спринт 14: Tasks v2 (импорт/экспорт, seed при старте, KI-010)

---

## Спринт 14: Tasks v2

**Период:** 2026-10-29  
**Статус:** ✅ Завершён

### Задачи
- [x] S14-001: Импорт/экспорт задач (JSON/YAML + CLI)
- [x] S14-002: Автонаполнение при старте (KI-010)
- [x] S14-003: Генерация задач через LLM с проверкой в песочнице
- [x] S14-004: Теги, поиск, категории
- [x] S14-005: Версии задач и откат
- [x] S14-006: Тесты и документация

### Что сделано
- **Импорт/экспорт:** `app/services/task_import.py`, JSON и YAML, массив или
  `{tasks: [...]}`; поштучная валидация, дубликаты по заголовку пропускаются;
  `POST /tasks/import`, `GET /tasks/export?format=json|yaml`,
  `scripts/import_tasks.py`
- **Seed:** данные в `app/data/seed_tasks.py`, сервис `seed_service`, флаг
  `SEED_ON_START` в lifespan, Docker Compose по умолчанию true; KI-010 закрыт
- **Генерация:** `POST /tasks/generate` (count ≤ 5), JSON-промпт, проверка
  эталонного решения в песочнице, отчёт `created/rejected`, usage в ответе
- **Теги/поиск:** `tasks.tags` JSONB + GIN (миграция 005), `?tag=&q=`,
  `GET /tasks/categories`
- **Версии:** `task_versions` (миграция 006), снимок перед правкой,
  `GET /tasks/{id}/versions`, откат с сохранением текущего состояния
- **Тесты:** 23 новых (импорт, seed, генерация, теги, версии)

### Что не сделано
- UI преподавателя для импорта/генерации — спринт 15 (Teacher Console)

### Метрики
- Backend: **250 passed** (+1 skip на Windows), было 227; ruff 0, mypy strict 0
- Покрытие: backend 83%
- Новые тесты: 23 backend
- Frontend: 65 unit (без изменений)
- Закрыто KI: **KI-010**

### Проблемы
- YAML добавлен зависимостью `PyYAML`; mypy-стабы не нужны (override в `pyproject.toml`)
- Генерация делает один LLM-вызов на запрос; при отказе всех задач повторов нет
  (осознанно: стоимость и предсказуемость)
- CI не стартовал (KI-014, биллинг GitHub) — локальные проверки зелёные

### Следующие шаги
- Спринт 15: Teacher Console (UI управления задачами)

---

## Спринт 15: Teacher Console

**Период:** 2026-10-29  
**Статус:** ✅ Завершён

### Задачи
- [x] S15-001: Страница управления задачами
- [x] S15-002: Форма задачи с конструктором тест-кейсов
- [x] S15-003: Импорт задач в UI
- [x] S15-004: Прогресс учеников для учителя
- [x] S15-005: Тесты и документация

### Что сделано
- **API учителя:** `GET /teacher/tasks` (включая неактивные),
  `GET /teacher/tasks/{id}`, `GET /teacher/students` (агрегаты),
  `GET /teacher/students/{id}/progress`; доступ teacher/admin, ученик — 403
- **UI:** `/teacher/tasks` — таблица, создание/правка, деактивация, импорт
  файла с предпросмотром; `/teacher/students` — таблица учеников и карточка
  прогресса; `TeacherRoute`, ссылка «Кабинет» в навигации
- **Импорт:** `POST /tasks/import/preview` и `/tasks/import/file` (multipart)
- **Тесты:** 6 backend + 6 frontend (71 всего)
- **Документация:** USER_GUIDE, SPEC, ARCHITECTURE, MANUAL_TESTING_GUIDE

### Что не сделано
- Кнопка «прогнать эталон» в форме — проверка эталона есть в генерации (S14-003)

### Метрики
- Backend: **256 passed** (+1 skip), ruff/mypy 0, покрытие **82%**
- Frontend: **71 passed**, typecheck/lint 0, entry 76.3 kB gzip
- Закрыто KI: нет (KI-013 — в S19)

### Проблемы
- CI не стартовал (KI-014, биллинг) — мерж по временному разрешению

### Следующие шаги
- Спринт 16: Classrooms & Assignments

---

## Спринт 16: Classrooms & Assignments

**Период:** 2026-10-30  
**Статус:** ✅ Завершён

### Задачи
- [x] S16-001: Модели и миграция 007
- [x] S16-002: API классов и вступления
- [x] S16-003: Назначения и «мои задания»
- [x] S16-004: Матрица прогресса класса
- [x] S16-005: UI классов и заданий
- [x] S16-006: Тесты и документация

### Что сделано
- **Модели:** `classrooms`, `classroom_members`, `assignments` (миграция 007),
  join_code, уникальность участника и задачи в классе
- **API:** создание/список/детали классов, вступление по коду, исключение
  участника, назначения, `/me/assignments`, `/classrooms/{id}/progress`
- **UI:** `/classrooms` (создание/вступление), `/classrooms/:id` (участники,
  назначения, матрица), `/assignments` (дедлайны, overdue)
- **Тесты:** 8 backend + 3 frontend
- **Документация:** SPEC, ARCHITECTURE, USER_GUIDE, MANUAL_TESTING_GUIDE

### Что не сделано
- Массовое назначение нескольких задач за один запрос
- Уведомления о назначениях — спринт 17

### Метрики
- Backend: **264 passed** (+1 skip), ruff/mypy 0, покрытие **80%**
- Frontend: **74 passed**, typecheck/lint/build 0, entry 77.2 kB gzip
- Закрыто KI: нет

### Проблемы
- Прогресс класса доступен только владельцу; участнику — 403 (осознанно)
- CI не стартовал (KI-014, биллинг) — мерж по временному разрешению

### Следующие шаги
- Спринт 17: Engagement (достижения, streak, дашборд)

---

## Спринт 17: Engagement

**Период:** 2026-10-30  
**Статус:** ✅ Завершён

### Задачи
- [x] S17-001: Достижения
- [x] S17-002: Streak и личная статистика
- [x] S17-003: Дашборд ученика
- [x] S17-004: In-app уведомления
- [x] S17-005: Тесты и документация

### Что сделано
- **Достижения:** `achievements`, `user_achievements` (миграция 008), 6 правил
  (первая задача, 10 задач, 3 дня подряд, все задачи сложности), выдача при
  submit, `GET /me/achievements`
- **Статистика:** `GET /me/stats` — решено, серия дней (UTC+3), средние
  попытки, сессии/сообщения чата
- **Дашборд:** `/dashboard` — прогресс-бар, streak, достижения, последние
  задачи, уведомления
- **Уведомления:** назначение задачи, дедлайн ≤72 ч, достижение;
  `GET /me/notifications`, `POST /me/notifications/{id}/read`
- **Тесты:** 7 backend + 2 frontend

### Что не сделано
- Email-уведомления (SMTP) — не блокируют in-app
- «Время в чате» не считается (нет длительности сессии) — отдаём сообщения

### Метрики
- Backend: **271 passed** (+1 skip), ruff/mypy 0, покрытие **80%**
- Frontend: **76 passed**, typecheck/lint/build 0, entry 77.7 kB gzip
- Закрыто KI: нет

### Проблемы
- Напоминания о дедлайне создаются лениво при `GET /me/notifications`
  (отдельного планировщика нет)
- CI не стартовал (KI-014, биллинг) — мерж по временному разрешению

### Следующие шаги
- Спринт 18: UX, A11y & Design System

---

## Спринт 18: UX, A11y & Design System

**Период:** 2026-10-30  
**Статус:** ✅ Завершён (2 задачи с оговорками)

### Задачи
- [x] S18-001: Дизайн-система
- [x] S18-002: Тёмная тема
- [x] S18-003: Доступность (WCAG AA)
- [x] S18-004: Мобильная адаптация
- [x] S18-005: Локализация (новые строки)
- [x] S18-006: Документация

### Что сделано
- **Токены и компоненты:** `--surface/--border/--app-fg`, `Modal`, `Toast`,
  `Tabs`, `Table`, `Badge`, `Skeleton`; dev-страница `/dev/ui` (вне прод-бандла)
- **Тёмная тема:** переключатель в шапке и профиле, `localStorage`, CSS-слой
  для всех экранов, Monaco `vs`/`vs-dark` на лету
- **Доступность:** skip-link, `main#main`, aria в модалке/табах/навигации,
  `vitest-axe` на входе и регистрации (0 нарушений)
- **Мобильность:** drawer сессий чата, мобильное меню, таблицы со скроллом
- **Локализация:** новые строки ru/en, переводы разделов классов/достижений
- **Тесты:** +4 (2 axe, 2 темы); всего 80 frontend

### Что не сделано
- Карточный вид таблиц на мобильных (горизонтальный скролл)
- Скрипт-аудит хардкода; 8 fallback-ошибок вне UI остаются русскими
- Автоматическая проверка контраста (jsdom не считает цвета) — чек-лист

### Метрики
- Backend: **271 passed** (+1 skip), покрытие **80%** (без изменений)
- Frontend: **80 passed**, typecheck/lint/build 0, entry 78.7 kB gzip

### Проблемы
- CI не стартовал (KI-014, биллинг) — мерж по временному разрешению

### Следующие шаги
- Спринт 19: Performance & Scale (Redis-кэш, запросы, pgvector, нагрузка)

---

## Спринт 19: Performance & Scale

**Период:** 2026-10-29 … 2026-10-30  
**Статус:** ✅ Завершён (S19-006: профиль зафиксирован; целевые 5 RPS `submit`
не достигнуты — knee ≈2 RPS, **KI-022**)

### Задачи
- [x] S19-001: Локальный Monaco без CDN (KI-013)
- [x] S19-002: Code splitting и lazy-маршруты
- [x] S19-003: Redis-кэш справочников и каталога задач
- [x] S19-004: Оптимизация запросов, индексы 0009/0010, пагинация
- [x] S19-005: Поиск по истории чата (pgvector, RAG-lite)
- [x] S19-006: Нагрузочный тест (httpx-генератор вместо k6/locust)
- [x] S19-007: Документация (ARCHITECTURE, README, RULES §11.18)

### Что сделано
- **Кэш (S19-003):** `app/services/cache.py` — `/chat/levels`,
  `/tasks/categories`, `/tasks`; TTL 60 с, ключ списка включает `user_id` и
  все фильтры; инвалидация namespace `cache:tasks:*` на CRUD/импорте/seed/
  откате; fail-open + 10 с cooldown; метрики `cache` в `/admin/analytics`
- **Оптимизация (S19-004):** N+1 в `/classrooms` и назначениях устранены
  агрегатами; пагинация `/classrooms`, `/me/notifications`, `/teacher/tasks`;
  индексы 0009 (каталог, ученики, уведомления, дедлайны, история сообщений),
  HNSW 0010; EXPLAIN-подтверждение через `enable_seqscan=off`
- **RAG-lite (S19-005):** `GET /chat/search` — семантический поиск по своим
  сообщениям (pgvector HNSW, `vector_cosine_ops`) за флагом `RAG_ENABLED`,
  ILIKE-fallback при выключенном/сбойном RAG; best-effort эмбеддинги через
  LM Studio `/embeddings`; изоляция по `chat_sessions.user_id` в репозитории
- **Нагрузка (S19-006):** `backend/scripts/load_test.py` (httpx, открытый
  цикл, 1 worker, `DEBUG=false`, `LLM_PROVIDER=echo`); `health` 50 RPS —
  p50 4.1 / p95 **6.3** мс, `tasks` 20 RPS — p50 12.9 / p95 **25.4** мс,
  0 ошибок (PASS); `submit` — факт 2.5 RPS, p50 1964 / p95 **2219.7** мс при
  бюджете 2000 мс (**FAIL по p95**), knee ≈2 RPS; бутылочное горлышко —
  песочница (3 процесса на submit × `EXECUTOR_MAX_CONCURRENCY=4` ≈2.3/s).
  Отчёт: `docs/reports/sprint-19/LOAD_TEST.md`; ограничение — **KI-022**
- **Frontend (S19-001/002):** Monaco офлайн (KI-013 закрыт), route-level
  code splitting, `pnpm test:offline`
- **Тесты:** `test_cache.py` (9), `test_rag_search.py` (10),
  `test_query_optimization.py` (7); autouse-фикстура `disable_cache`

### Что не сделано
- RAG с живой embedding-моделью не проверен: LM Studio с embedding-моделью не
  поднят (причина KI-008); провайдер абстрагирован и покрыт фейком
- Нет backfill эмбеддингов для сообщений до включения RAG; нет порога
  релевантности (`RAG_MIN_SCORE`) — semantic всегда отдаёт top-k
- Кэш каталога зависит от прогресса пользователя: после submit статус может
  отставать до TTL (осознанно)
- Метрики кэша — в памяти процесса (как `llm`): при нескольких воркерах
  каждый показывает только свои счётчики
- EXPLAIN снят на почти пустых таблицах; полноценный профиль — только
  нагрузочный отчёт
- Целевые 5 RPS `submit` не достигнуты (knee ≈2 RPS, p95 2219.7 мс > бюджета
  2000 мс) — ограничение песочницы, зарегистрировано **KI-022**; рекомендации
  (один процесс на все кейсы, пул интерпретаторов, поднять concurrency,
  очередь с 429/503) — в LOAD_TEST §5, код не менялся в S19

### Метрики
- Backend: **341 passed** (+1 skip на Windows; 342 collected, 200.41 с —
  финальный прогон v0.2.0), ruff 0, mypy strict 0 (76 модулей)
- Frontend: **80 unit** + **12 e2e**; entry **78.71 kB gzip** (react 15.30,
  i18n 18.40), `pnpm test:offline` — passed
- Миграции: **003 → 010** (`upgrade head`), `alembic check` — «No new upgrade
  operations detected», цикл downgrade→upgrade — 4 passed
- Нагрузка: `health` p95 6.3 мс (50 RPS ✅), `tasks` p95 25.4 мс (20 RPS ✅),
  `submit` p95 2219.7 мс при факте 2.5 RPS (5 RPS ❌, **KI-022**)
- Покрытие: порог backend 70% (последний замер — 80%, S18)

### Проблемы / уроки
- Fail-open кэша без cooldown превращался бы в timeout на каждом запросе —
  добавлены 10 с «остывания» и отдельные счётчики ошибок
- Ключ списка задач обязан включать `user_id`: иначе кэш «протекает» между
  учениками (статус прогресса в ответе)
- Ivfflat на пустой таблице бесполезен (нужны обучающие данные) — выбран
  HNSW, он строится сразу и поддерживает `vector_cosine_ops`
- Локальный PyPI заблокирован → k6/locust не поставить, нагрузочный раннер
  написан на httpx (см. RULES §11.18)

### DoD
- ✅ Кэш с инвалидацией и метриками, fail-open; пагинация без регрессий;
  индексы подтверждены EXPLAIN; `/chat/search` работает в двух режимах и
  изолирован; нагрузочный профиль зафиксирован (health/tasks PASS, submit —
  knee ≈2 RPS, **KI-022**); KI-013 закрыт; документация обновлена

### Закрыто KI
- **KI-013** (Monaco с CDN)

### Следующие шаги
- Спринт 20: Security Audit & Release v0.2.0

---

## Спринт 20: Security Audit & Release

**Период:** 2026-10-30  
**Статус:** ✅ Завершён (S20-003 — 35 тестов, IDOR не найден; финальный тег
`v0.2.0` — за релиз-инженером, CI — KI-014)

### Задачи
- [x] S20-001: Аудит зависимостей backend/frontend, устранение High/Critical
- [x] S20-001b: RestrictedPython 7.4 → 8.5 (3 high обхода песочницы)
- [x] S20-002: Секреты, gitleaks, CSP/security headers, prod-конфиг
- [x] S20-003: Аудит прав доступа и IDOR (35 тестов; IDOR не найден; F1 исправлена)
- [x] S20-004: Бэкапы и восстановление (`scripts/backup.sh`/`restore.sh`)
- [x] S20-005: Финальная документация v0.2.0
- [x] S20-006: Полная проверка и релиз (локальные гейты; тег — Lead)

### Что сделано
- **Зависимости (S20-001):** frontend `vitest`/`coverage` 3.2.7 → 4.1.12
  (2 critical + 3 moderate закрыты, `pnpm audit` — 0); backend —
  `python-jose` удалён → **PyJWT 2.15.1**, `python-multipart` **0.0.31**,
  **RestrictedPython 8.5**; `pip-audit` (Docker/CI-путь): **66 записей в 7
  пакетах → 16 записей в 2 пакетах, 0 critical** (остатки — starlette и
  dev-only pytest, KI-015/KI-016); Dependabot; локальный
  `audit_python_deps.py` для машины без PyPI
- **Секреты/конфиг (S20-002):** `.gitleaks.toml` + CI job `Security`;
  скан истории — **0 утечек на 42 коммитах**; `.env`/`backups/` в
  `.gitignore`; prod-compose: обязательные секреты (`:?`), `DEBUG=false`,
  БД/Redis без публикации портов, `ALLOWED_ORIGINS` из ENV
- **CSP/заголовки:** CSP (без `unsafe-eval`), `nosniff`, `DENY`,
  `strict-origin-when-cross-origin`, `Permissions-Policy`, HSTS,
  `server_tokens off`; проверено `nginx -t` и Playwright (Monaco грузится,
  worker'ы `blob:`); `index.html` — `no-cache`
- **Доступ (S20-003):** матрица «эндпоинт × роль» + IDOR по всем сущностям —
  **35 тестов, IDOR не найден**; автотест `test_access_matrix.py`; исправлена
  находка F1 (LOW): анонимный `GET /tasks/{id}/hints/{index}` → теперь 403 без
  заголовка `Authorization` (401 — невалидный токен)
- **Бэкапы (S20-004):** `backup.sh`/`restore.sh` (docker exec pg_dump, gzip,
  sha256, retention 14 дней, guard рабочей БД, `--create`/`--verify`);
  smoke — **14/14 таблиц**, счётчики совпали; документация в
  GETTING_STARTED §8 и DESIGN_ADMIN_AND_OPS §6/§7
- **Документация (S20-005):** SPEC (кэш/RAG/пагинация/безопасность/бэкапы/
  критерии v0.2.0), CHANGELOG `[0.2.0]`, RELEASES (19/20 + релиз),
  KNOWN_ISSUES (KI-015…KI-022), RULES §11.18–11.19, MANUAL_TESTING_GUIDE,
  README/GETTING_STARTED, USER_GUIDE; отчёт

### Что не сделано
- GitHub Actions job'ы (включая `Security` и `e2e`) не запускались —
  KI-014 (биллинг Actions); локальные эквиваленты проверок выполнены
- Координированный апгрейд `fastapi`/`starlette` отложен (KI-015, v0.3.0,
  Dependabot PR); dev-апгрейд `pytest` 9.x — KI-016
- Docker prod build+smoke и тег `v0.2.0` — финальный гейт Lead
 
### Метрики
- Frontend: **80/80** unit, typecheck/lint/build — 0, entry **78.71 kB gzip**,
  `pnpm audit` — 0; **e2e 12/12** (Playwright, ~1.2 мин, провайдер `echo`,
  отдельная БД `ai_teacher_e2e`)
- Backend: **341 passed** (+1 skip; 342 collected, 200.41 с), ruff 0,
  mypy strict 0
- Аудит backend: `pip-audit` — 0 critical; 16 записей в 2 пакетах (принято,
  KI-015/KI-016); CI-команда с 8 ignores — «No known vulnerabilities found,
  16 ignored», exit 0
- gitleaks: 0 утечек / 42 коммита; nginx: `nginx -t` OK, 6 заголовков;
  backup/restore: 14/14 таблиц; Docker build: успешно (PyJWT 2.15.1,
  multipart 0.0.31, python-jose отсутствует)

### Проблемы
- PyPI с хоста заблокирован → pip-audit только в Docker, локальный аудит
  через GitHub Advisory API (лимит 60/час) — KI-017
- RestrictedPython 8.5 запретил `.format()`/`format_map()`/`string.Formatter`
  → user-visible ограничение, подсказка `RestrictedFeatureError` — KI-018
- `starlette 0.41.3` тянется от `fastapi 0.115.5`: апгрейд требует мажорного
  coordinated-апгрейда и полного прогона тестов — принят риск KI-015
- CI-job `Security` использует временный `--ignore-vuln` (8 ID: 7 starlette +
  1 pytest); после апгрейдов игноры убрать
- Локальный venv (3.11) ставился без PyPI: `restrictedpython`/`starlette`/
  `pytest` обновлялись вручную через Docker-wheelhouse — версии сверять с CI

### DoD
- ✅ 0 critical по зависимостям; high только в транзитивном starlette с
  неприменимыми векторами (принято и отслеживается); бэкап/восстановление
  проверены; security-заголовки живые; секретов в git нет; документация
  v0.2.0 актуальна; backend **341 passed + 1 skip**, frontend 80/80 и e2e
  **12/12** — зелёные; Docker prod smoke и тег `v0.2.0` — финальный шаг Lead
  (CI — KI-014)

### Закрыто KI
- **KI-019** (python-jose/PyJWT/python-multipart), **KI-020** (vitest/tinypool),
  **KI-021** (RestrictedPython 7.4 → 8.5); новые принятые риски — KI-015…KI-018

### Следующие шаги
- v0.3.0: coordinated fastapi/starlette upgrade (KI-015), dev pytest 9.x
  (KI-016), backfill эмбеддингов/порог RAG, восстановление CI (KI-014)

---

## Релиз v0.2.0 «Classroom»

**Дата:** 2026-10-30 · **Тег:** `v0.2.0` · **Предыдущий:** [v0.1.0](#спринт-10-admin--polish--релиз-v010)

### Что вошло
- **Для класса:** классы и вступление по коду, назначения с дедлайнами,
  матрица прогресса класса, кабинет учителя (задачи/импорт/ученики)
- **Вовлечение:** достижения, streak и `/me/stats`, дашборд, in-app уведомления
- **UX:** тёмная тема, дизайн-система, WCAG AA (skip-link, aria, axe),
  мобильный чат/drawer
- **Производительность:** локальный Monaco без CDN, code splitting,
  Redis-кэш, индексы и пагинация, поиск по истории чата (RAG-lite)
- **Безопасность:** аудит зависимостей (0 critical), CSP/security headers,
  gitleaks + CI job `Security`, Dependabot, backup/restore, `.format()`
  заблокирован в песочнице как плата за закрытые обходы RP 8.5

### Метрики
| Показатель | Значение |
|------------|----------|
| Backend-тесты | **341 passed** (+1 skip; 342 collected) |
| Frontend-тесты | 80 unit + 12 e2e (12/12 green) |
| Миграции | 001 → 010, `alembic check` чист |
| Entry-бандл | 78.71 kB gzip (≤ 80) |
| Зависимости | frontend 0 vulns; backend 0 critical, 16 accepted-записей (KI-015/KI-016) |
| Нагрузка (S19-006) | health 50 RPS p95 6.3 мс ✅ · tasks 20 RPS p95 25.4 мс ✅ · submit 2.5 RPS p95 2219.7 мс ❌ (knee ≈2 RPS, KI-022) |
| Матрица доступа (S20-003) | 35 тестов, IDOR не найден |

### Известные ограничения релиза
- KI-014 — GitHub Actions не запускает job'ы (биллинг); локальные проверки
  (backend 341/1, frontend 80/80, e2e 12/12, аудит, gitleaks, nginx, backup)
  выполнены; Docker prod smoke и зелёный CI на GitHub — после восстановления
  оплаты/финального гейта
- KI-015/016 — принятые остаточные риски зависимостей (starlette/fastapi,
  dev pytest); KI-017 — PyPI недоступен с хоста; KI-018 — `.format()` в
  песочнице запрещён
- RAG: нет backfill эмбеддингов и порога релевантности; живая embedding-модель
  не проверялась (провайдер покрыт фейком)
- Submit: целевые 5 RPS не достигнуты (knee ≈2 RPS, p95 2219.7 мс) —
  ограничение песочницы, KI-022; health/каталог с запасом 47×/12×
- Матрица доступа S20-003: 35 тестов, IDOR не найден, F1 (LOW) исправлена;
  отсутствие заголовка `Authorization` → 403 (`HTTPBearer`), невалидный
  токен → 401

### Документация релиза
[CHANGELOG.md](CHANGELOG.md#020---2026-10-30) ·
[KNOWN_ISSUES.md](KNOWN_ISSUES.md) ·
[reports/sprint-19/SPRINT-19.md](reports/sprint-19/SPRINT-19.md) ·
[reports/sprint-20/SPRINT-20.md](reports/sprint-20/SPRINT-20.md) ·
[MANUAL_TESTING_GUIDE.md](MANUAL_TESTING_GUIDE.md)

---

## Спринт 21: CI & Quality Gates

**Период:** 2026-10-30  
**Статус:** ✅ CI восстановлен (6/6 job'ов на self-hosted runner'е); merge-gate
на GitHub Free невозможен — GitFlic-пилот ждёт доступа владельца (KI-023),
S21-002/S21-004 закрыты частично

### Задачи
- [x] S21-001: Диагностика GitHub (аннотация API, причин — биллинг) и ADR
- [~] S21-002: Пилот GitFlic — импорт выполнен, конфиги/рунбук/скрипты готовы;
      живой прогон ждёт access token и агента (Java 11 + регистрация)
- [x] S21-003: CI работает — 6 job'ов на self-hosted runner'е (GitFlic-порт готов)
- [~] S21-004: Path-фильтры и скрипт защиты ветки готовы; автоматический
      required-check гейт невозможен без Pro/публичного репо или GitFlic
      (KI-023)
- [x] S21-005: Release-workflow (гейты → тег → GitHub Release), dry-run,
      заметки из `docs/RELEASES.md`; GitFlic-джоб `release` — тег-пайплайн
- [x] S21-006: `docs/CI.md`, RULES §10/§11.20, README-бейдж, CHANGELOG,
      KNOWN_ISSUES, отчёты

### Что сделано
- **Диагностика (S21-001):** причина падений подтверждена аннотацией API
  (`check-runs/<job>/annotations`): «recent account payments have failed or your
  spending limit needs to be increased» — KI-014. Токен `gh` без scope `user`,
  поэтому billing-API недоступен из CLI (инструкция — `docs/CI.md` §1).
- **CI (S21-003):** установлен self-hosted runner `ai-teacher-win`
  (`C:\actions-runner`, labels `self-hosted, windows, ai-teacher`), workflow
  `CI (self-hosted fallback)` — 6 job'ов, прогон **6/6 зелёный**
  ([run 41070317162](https://github.com/iilmchat/ai-teacher_python/actions/runs/41070317162),
  12 мин 10 с). Job'ы используют общие `scripts/ci/*`, кэш pip/pnpm — named
  volumes, плюс офлайн-wheelhouse (KI-017): PyPI с машины нестабилен.
- **GitHub-hosted `ci.yml`** переведён в ручной режим: hosted-минуты заблокированы
  биллингом, красный workflow не должен висеть на каждом PR; возврат — одна
  правка `on:` после оплаты (KI-014, `docs/CI.md` §9).
- **GitFlic (S21-002):** проект импортирован
  (`gitflic.ru/project/ruchating/ai-teacher_python`, `main` = `5a74145`);
  `gitflic-ci.yaml` — порт 5 job'ов + 3 security-job'а, `e2e`/`docker` на
  PowerShell-агенте, path-фильтры, тег-джоб `release`; пилотный
  `ci/gitflic-pilot.yaml` (lint+test с `services`); рунбук
  `docs/GITFLIC_RUNNER.md`; настройка переменных и агента —
  `scripts/gitflic/setup.ps1`. Локально команды всех job'ов прогнаны в тех же
  Docker-образах (§8 `docs/CI.md`): lint/test/frontend/e2e 12/12/docker — PASS.
- **Гейты (S21-004):** `paths-ignore` (docs-only PR не гоняет e2e/docker);
  `scripts/ci/protect-branch.ps1` — 6 required checks + запрет force-push,
  честный exit 3 на 403 Free/private.
- **Релиз (S21-005):** `.github/workflows/release.yml` переиспользует
  `ci-selfhosted.yml` через `workflow_call`; версия сверяется в трёх файлах
  (`backend/scripts/check_version.py`), заметки — раздел «## Релиз vX.Y.Z» из
  `docs/RELEASES.md` (`backend/scripts/release_notes.py`); dry-run по умолчанию
  и для тега `v*-dryrun`; реальный релиз — `workflow_dispatch` с
  `dry_run=false` (тег + `gh release create --verify-tag`).
- **Документация (S21-006):** `docs/CI.md` (ADR, гейты, релиз, эксплуатация
  runner'а, офлайн-путь), RULES §2.3/§5.1/§10/§11.19/§11.20, README-бейдж,
  CHANGELOG `[Unreleased]`, KNOWN_ISSUES (KI-014 → Resolved, KI-023), отчёты
  `docs/reports/sprint-21/STEP-04_QUALITY_GATES_RELEASE.md` и `SPRINT-21.md`.

### Что не сделано
- **Живой пилот GitFlic** (S21-002): импорт есть, но CI/CD проекта, агент
  (нужны Java 11 + registration token) и MR-пайплайн требуют access token
  владельца. Команды job'ов проверены локально, но `services`, маскировка
  секретов и MR-пайплайн на платформе не подтверждены — KI-023.
- **Автоматический merge-gate** (S21-004): GitHub Free/private → required checks
  403; GitFlic даёт гейт бесплатно, но его проверка — после пилота — KI-023.
- **Живой `workflow_dispatch`-релиз** — файла нет в `default`-ветке до мержа
  спринта; репетиция выполнена тегом `v0.2.0-dryrun` (run 41126158359, зелёный).
  Ветка «реальный релиз» (тег + `gh release create`) впервые пройдёт на v0.3.0.
- **Playwright-кэш в CI** не выделен отдельным томом: браузеры стоят в профиле
  пользователя runner'а и между прогонами не пересоздаются.

### Метрики
- CI (self-hosted): **6/6 job'ов success**, run 41122794849 — 11 мин 53 с;
  Frontend 50 с, Security 1 мин 17 с, Lint 32 с, Test 1 мин 56 с (354 passed
  + 1 skip), Docker build 5 мин 55 с (pip внутри Dockerfile — PyPI), E2E
  1 мин 5 с (**12/12**)
- Release dry-run: run 41126158359 — 6/6 гейтов + `Tag & Release` success
- Backend: +13 тестов (`tests/test_release_tools.py`), ruff 0 (скоуп
  `app tests scripts`), mypy strict 0
- Frontend: 80/80 unit, entry **78.71 kB gzip** (без изменений в коде)
- Артефакты CI: `notes.md` (GitFlic-тег), Playwright-репорт (7 дней)

### Проблемы
- **KI-023 (High):** merge-gate не обеспечен — GitHub Free/private + GitFlic
  ждёт доступ. Workaround: RULES §10 (мерж только при зелёном fallback-CI).
- **KI-017:** PyPI с машины стал ещё нестабильнее — job `lint` залипал в
  `pip install` на 20+ минут (TLS-таймауты). Решение: wheelhouse (named volume)
  + кэши pip/pnpm; PyPI — только fallback.
- **Лишний red-шум:** hosted-`ci.yml` отключён от PR (иначе красный на каждом
  PR из-за биллинга); при возврате hosted-минут — снять `workflow_dispatch`-only.
- **Кэш Actions на self-hosted** не используется намеренно (named volumes
  проще); при переезде в GitFlic кэш — локальный на Docker-агенте.

### DoD
- ⚠️ Красный PR не мержится **автоматически** — невозможно на GitHub
  Free/private и в ожидании GitFlic (KI-023); правило RULES §10 действует.
- ✅ 6 job'ов CI зелёные (run 41122794849); локальные гейты v0.3.0 не сломаны.
- ✅ Release dry-run выполнен живьём (run 41126158359, тег `v0.2.0-dryrun`);
  реальная ветка релиза — на v0.3.0 (S30-004).
- ✅ `docs/CI.md` описывает процессы и решение; KI-014 → `Resolved`; KI-023
  заведена с планом.

---

## Шаблон отчёта по спринту

```
## Спринт N: Название

**Период:** YYYY-MM-DD - YYYY-MM-DD
**Статус:** ✅ Завершён / ⚠️ Частично / ❌ Блокер

### Задачи
- [x] Выполненные задачи
- [~] В процессе
- [ ] Не начато

### Что сделано
- Список выполненных работ

### Что не сделано
- Причины и ссылки на KI-NNN

### Метрики
- Тесты: X/Y passed
- Ruff / MyPy: 0/0
- CI: green/red

### Проблемы
- Описание проблем и их решение

### Следующие шаги
- План следующего спринта
```
