# RELEASES.md — Журнал спринтов

> Этот документ содержит историю всех спринтов и релизов проекта.

**Текущая версия:** v0.1.0 (выпущена)  
**Текущий спринт:** этап v0.1.0 завершён; следующий — спринт 11 по [TODO_V0.2.md](../TODO_V0.2.md)

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
- [Следующий этап: v0.2.0](#следующий-этап-v020-classroom-планируется)
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

## Следующий этап: v0.2.0 «Classroom» (планируется)

**План:** [../TODO_V0.2.md](../TODO_V0.2.md) — спринты 11–20, ~24 дня.

| Спринт | Тема | Закрывает |
|--------|------|-----------|
| 11 | Quality Gates & E2E | KI-001, KI-002, KI-006, KI-007, KI-012 |
| 12 | LLMOps | KI-008 |
| 13 | Sandbox Hardening | KI-009 |
| 14 | Tasks v2 | KI-010 |
| 15 | Teacher Console | — |
| 16 | Classrooms & Assignments | — |
| 17 | Engagement | — |
| 18 | UX, A11y & Design System | — |
| 19 | Performance & Scale | KI-013 |
| 20 | Security Audit & Release | — |

Порядок обязателен: спринты 11–13 закрывают технический долг, только затем
добавляется функциональность (14–18) и оптимизации (19–20).

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
