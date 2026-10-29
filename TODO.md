# TODO.md — AI Teacher for Python

> Этот документ — план разработки проекта. Каждая задача имеет ID, зависимости и статус.
> Статусы: `[ ]` — не начато, `[~]` — в работе, `[x]` — завершено, `[!]` — блокер (см. KNOWN_ISSUES.md)

**Версия:** v0.1.0  
**Последнее обновление:** 2026-10-29  
**Текущий спринт:** завершены все 10 спринтов  
**Готово:** Спринты 1–10 (backend, frontend, админка, документация, релиз v0.1.0)

---

## Оглавление

1. [Спринт 1: Project Setup](#спринт-1-project-setup-день-1)
2. [Спринт 2: Backend Core](#спринт-2-backend-core-день-2-3)
3. [Спринт 3: Authentication](#спринт-3-authentication-день-4)
4. [Спринт 4: Chat Service](#спринт-4-chat-service-день-5-6)
5. [Спринт 5: Three Levels](#спринт-5-three-levels-день-7)
6. [Спринт 6: Code Execution](#спринт-6-code-execution-день-8)
7. [Спринт 7: Task System](#спринт-7-task-system-день-9)
8. [Спринт 8: Frontend Base](#спринт-8-frontend-base-день-10-11)
9. [Спринт 9: Frontend Features](#спринт-9-frontend-features-день-12-13)
10. [Спринт 10: Admin & Polish](#спринт-10-admin--polish-день-14-15)

---

## Спринт 1: Project Setup (День 1)

**Цель:** Создать базовую структуру проекта, настроить окружение и CI/CD.

### S1-001: Создание структуры директорий — ✅
- [x] Создать корневую структуру проекта
- [x] Создать директории backend/app/*, frontend/src/*, docs/*
- [x] Создать пустые __init__.py файлы
- [x] Создать .gitignore для Python и Node.js
- [x] **Зависит от:** нет
- [x] **Оценка:** 30 мин

### S1-002: Настройка Python окружения — ✅
- [x] Создать pyproject.toml с зависимостями (FastAPI, SQLAlchemy, Pydantic, etc.)
- [x] Создать requirements.txt для Docker
- [x] Настроить ruff и mypy конфигурацию
- [ ] Создать .python-version для pyenv (не требуется: venv в backend/)
- [x] **Зависит от:** S1-001
- [x] **Оценка:** 30 мин

### S1-003: Docker Compose конфигурация — ✅
- [x] Создать docker-compose.yml (PostgreSQL, Redis, backend, frontend)
- [x] Создать .env.example с переменными окружения
- [x] Создать Dockerfile для backend
- [ ] Создать Dockerfile для frontend (отложено до спринта 8)
- [x] Протестировать docker compose up (postgres + redis healthy)
- [x] **Зависит от:** S1-002
- [x] **Оценка:** 1 час

### S1-004: Git и CI/CD — ✅
- [x] Инициализировать git репозиторий
- [x] Создать ветку main
- [x] Создать .github/workflows/ci.yml (lint, test, build)
- [ ] Создать .github/workflows/deploy.yml (опционально, отложено)
- [x] Создать первый коммит
- [x] **Зависит от:** S1-001, S1-002, S1-003
- [x] **Оценка:** 1 час

### S1-005: Документация — ✅
- [x] Создать README.md с описанием проекта
- [x] Создать docs/RULES.md (адаптировать из ai-chess-annotator)
- [x] Создать docs/KNOWN_ISSUES.md (пустой шаблон)
- [x] Создать docs/CHANGELOG.md (инициализация)
- [x] **Зависит от:** S1-001
- [x] **Оценка:** 30 мин

### S1-006: Pre-commit hooks — ⏳ перенесено
- [ ] Настроить Husky или pre-commit
- [ ] Добавить хуки: ruff, mypy, prettier
- [ ] Добавить проверку секретов (detect-secrets)
- [ ] **Зависит от:** S1-002
- [ ] **Оценка:** 30 мин
- **Статус:** перенесено; проверки выполняются вручную по чек-листу RULES §10 и в CI

---

## Спринт 2: Backend Core (День 2-3)

**Цель:** Создать базовый FastAPI проект с подключением к PostgreSQL и Redis.

### S2-001: FastAPI приложение — ✅
- [x] Создать app/main.py с FastAPI приложением
- [x] Создать app/config.py с настройками (pydantic-settings)
- [x] Создать app/dependencies.py для DI
- [x] Добавить healthcheck эндпоинт
- [x] Добавить CORS middleware
- [x] **Зависит от:** S1-002
- [x] **Оценка:** 1 час

### S2-002: PostgreSQL + SQLAlchemy — ✅
- [x] Создать app/db/database.py (async engine)
- [x] Создать app/db/session.py (async session maker)
- [x] Создать базовую модель с UUID и timestamps
- [x] Настроить пул соединений
- [x] **Зависит от:** S2-001
- [x] **Оценка:** 1.5 часа
- **Примечание:** session maker находится в `app/db/database.py`

### S2-003: Redis подключение — ⚠️ частично
- [ ] Создать app/db/redis.py (async redis client)
- [ ] Добавить healthcheck для Redis
- [ ] Создать утилиты для кэширования
- [x] **Зависит от:** S2-001
- [x] **Оценка:** 1 час
- **Статус:** настроены URL и порт (6381), клиент и healthcheck перенесены в спринт 4

### S2-004: Alembic миграции — ✅
- [x] Инициализировать Alembic
- [x] Создать начальную миграцию (пустую)
- [x] Протестировать upgrade/downgrade
- [x] **Зависит от:** S2-002
- [x] **Оценка:** 1 час
- **Проверено:** `upgrade head` → `downgrade base` → `upgrade head` → `alembic check` (0 расхождений)

### S2-005: Модели данных (User, ChatSession, ChatMessage) — ✅
- [x] Создать app/models/user.py
- [x] Создать app/models/chat.py
- [x] Создать миграцию для моделей
- [x] Добавить индексы
- [x] **Зависит от:** S2-002, S2-004
- [x] **Оценка:** 2 часа
- **Исправлено:** enum через `values_callable` (KI-004), `metadata` → `session_metadata`

### S2-006: Pydantic схемы — ✅
- [x] Создать app/schemas/user.py
- [x] Создать app/schemas/chat.py
- [x] Добавить валидацию (email, длина пароля ≤ 72 байт)
- [x] **Зависит от:** S2-005
- [x] **Оценка:** 1 час

### S2-007: Репозитории — ✅
- [x] Создать app/db/repositories/base.py (BaseRepository)
- [x] Создать app/db/repositories/user.py
- [x] Создать app/db/repositories/chat.py
- [x] **Зависит от:** S2-005, S2-006
- [x] **Оценка:** 1.5 часа

### S2-008: Тесты Backend Core — ✅
- [x] Создать tests/conftest.py (fixtures на реальном PostgreSQL)
- [x] Создать tests/test_health.py
- [ ] Создать tests/test_db.py (покрыто интеграционными тестами auth)
- [x] Настроить pytest-asyncio
- [x] **Зависит от:** S2-001, S2-002, S2-003
- [x] **Оценка:** 1 час

---

## Спринт 3: Authentication (День 4)

**Цель:** Реализовать JWT аутентификацию с ролями.

### S3-001: Security модуль — ✅
- [x] Создать app/core/security.py
- [x] Реализовать хэширование паролей (bcrypt — вместо passlib, KI-005)
- [x] Реализовать JWT токены (access + refresh)
- [x] Реализовать валидацию токенов
- [x] **Зависит от:** S2-001
- [x] **Оценка:** 1.5 часа

### S3-002: Auth API endpoints — ✅
- [x] Создать app/api/v1/auth.py
- [x] POST /api/v1/auth/register
- [x] POST /api/v1/auth/login (по username или email)
- [x] POST /api/v1/auth/logout
- [x] POST /api/v1/auth/refresh
- [x] GET /api/v1/auth/me
- [x] PATCH /api/v1/auth/me
- [x] **Зависит от:** S3-001, S2-006
- [x] **Оценка:** 2 часа

### S3-003: Role-Based Access Control (RBAC) — ✅
- [x] Добавить роли в модель User (student, teacher, admin)
- [x] Создать фабрику зависимостей require_role
- [x] Создать middleware для проверки токена (HTTPBearer)
- [ ] Добавить проверки в endpoints (появится вместе с админ-эндпоинтами, спринт 10)
- [x] **Зависит от:** S3-001, S2-005
- [x] **Оценка:** 1.5 часа

### S3-004: Rate Limiting — ⚠️ частично
- [x] Создать app/core/rate_limiter.py
- [x] Настроить лимиты: login (5/мин), общий (300/мин)
- [x] Интегрировать с Redis (использует redis.asyncio)
- [ ] Добавить middleware в приложение (перенесено в спринт 4 — нужен Redis-клиент в lifespan)
- [x] **Зависит от:** S2-003
- [x] **Оценка:** 1 час

### S3-005: Тесты Authentication — ✅
- [x] tests/test_auth.py (14 тестов вместо 4 файлов)
- [x] Проверка регистрации, дублей, валидации
- [x] Проверка login/logout/refresh/me
- [ ] tests/test_rate_limiter.py (перенесено вместе с подключением middleware)
- [x] **Зависит от:** S3-002, S3-003, S3-004
- [x] **Оценка:** 1.5 часа

---

## Спринт 4: Chat Service (День 5-6)

**Цель:** Реализовать чат-сервис с интеграцией LLM.

### S4-001: LLM Provider Interface — ✅
- [x] Создать app/services/llm/base.py (абстрактный класс, LLMMessage, ошибки)
- [x] Создать app/services/llm/deepseek.py
- [x] Создать app/services/llm/lm_studio.py
- [x] Добавить конфигурацию провайдеров (фабрика create_llm_provider)
- [x] **Зависит от:** S2-001, S2-002
- [x] **Оценка:** 2 часа

### S4-002: Chat Service — ✅
- [x] Создать app/services/chat_service.py
- [x] Реализовать создание сессии
- [x] Реализовать отправку сообщения (generate + stream_reply)
- [x] Реализовать получение истории
- [x] **Зависит от:** S2-007, S4-001
- [x] **Оценка:** 2 часа

### S4-003: Prompt Management — ✅
- [x] Создать app/services/llm/prompts/ директорию
- [x] Создать базовый промпт (+ intermediate, advanced)
- [x] Создать систему подстановки переменных (prompt_builder.build_messages)
- [ ] Версионирование промптов (файлы под git; отдельные версии — в спринте 5)
- [x] **Зависит от:** S4-001
- [x] **Оценка:** 1.5 часа

### S4-004: Context Management — ✅
- [x] Реализовать сбор контекста из истории чата
- [x] Добавить truncation (последние 20 сообщений, 4000 символов на сообщение)
- [x] Добавить injection системного промпта
- [x] **Зависит от:** S4-002
- [x] **Оценка:** 1 час

### S4-005: Chat API — ✅
- [x] Создать app/api/v1/chat.py
- [x] POST /api/v1/chat/sessions
- [x] GET /api/v1/chat/sessions
- [x] GET /api/v1/chat/sessions/{id}
- [x] DELETE /api/v1/chat/sessions/{id}
- [x] POST /api/v1/chat/sessions/{id}/messages
- [x] **Зависит от:** S4-002, S2-006
- [x] **Оценка:** 2 часа

### S4-006: WebSocket для чата — ⚠️ частично
- [x] Создать app/api/websocket.py
- [x] Реализовать streaming ответов LLM (start/token/done/error)
- [x] Добавить heartbeat (ping/pong)
- [x] Добавить error handling
- [ ] Интеграционный тест полного стриминга (см. KI-006)
- [x] **Зависит от:** S4-005
- [x] **Оценка:** 2 часа

### S4-007: Тесты Chat Service — ⚠️ частично
- [x] tests/test_chat.py (сессии, сообщения, доступ, контекст)
- [x] tests/test_prompts.py (промпты, контекст, извлечение кода)
- [x] tests/test_websocket.py (авторизация WS)
- [ ] Отдельный файл тестов провайдеров (покрыто фабрикой в test_prompts.py)
- [x] **Зависит от:** S4-005, S4-006
- [x] **Оценка:** 2 часа

---

## Спринт 5: Three Levels (День 7)

**Цель:** Реализовать три уровня ассистента с разными промптами.

### S5-001: Level-specific Prompts — ✅
- [x] Создать app/services/llm/prompts/basic.txt
- [x] Создать app/services/llm/prompts/intermediate.txt
- [x] Создать app/services/llm/prompts/advanced.txt
- [ ] Протестировать каждый уровень вручную с реальной LLM (нужен API-ключ, KI-008)
- [x] **Зависит от:** S4-003
- [x] **Оценка:** 2 часа

### S5-002: Level Management — ✅
- [x] Добавить поле level в User и ChatSession (было с S2-005)
- [x] Реализовать переключение уровня (PATCH /users/me/level)
- [x] Добавить валидацию уровня (Pydantic Enum + parse_level)
- [x] Обновить схемы (ChatSessionCreate.level теперь Optional)
- [x] **Зависит от:** S2-005, S4-002
- [x] **Оценка:** 1 час

### S5-003: Level-aware Response Generation — ✅
- [x] Интегрировать выбор промпта в ChatService
- [x] Добавить метаданные уровня в ответ (GET /users/me/level, /chat/levels)
- [x] Реализовать fallback логику (resolve_level → basic при отсутствии промпта)
- [x] **Зависит от:** S5-001, S5-002
- [x] **Оценка:** 1.5 часа

### S5-004: Level API — ✅
- [x] PATCH /api/v1/users/me/level
- [x] GET /api/v1/chat/levels (информация о уровнях)
- [x] GET /api/v1/users/levels (тот же справочник в профиле)
- [x] Обновить POST /api/v1/chat/sessions (параметр level необязателен)
- [x] **Зависит от:** S5-002
- [x] **Оценка:** 1 час

### S5-005: Тесты Levels — ✅
- [x] tests/test_levels.py (14 тестов: чистые функции + API)
- [x] Проверка переключения уровня и наследования сессией
- [x] Проверка fallback и справочника уровней
- [x] **Зависит от:** S5-003, S5-004
- [x] **Оценка:** 1.5 часа

---

## Спринт 6: Code Execution (День 8)

**Цель:** Реализовать безопасное выполнение Python кода.

### S6-001: Sandboxed Executor — ✅
- [x] Создать app/core/executor.py
- [x] Интегрировать RestrictedPython + изоляция в отдельном процессе
- [x] Реализовать timeout (5 сек, процесс убивается)
- [ ] Реализовать memory limit (128 MB) — на Windows не enforced, см. KI-009
- [x] **Зависит от:** S2-001
- [x] **Оценка:** 2.5 часа

### S6-002: Safe Builtins — ✅
- [x] Создать whitelist разрешённых модулей (12 модулей)
- [x] Создать whitelist разрешённых функций (safe_builtins + безопасные дополнения)
- [x] Заблокировать опасные операции (os, sys, subprocess, open, eval, exec)
- [ ] Добавить логирование попыток нарушения (логгирование в API — в спринте 7)
- [x] **Зависит от:** S6-001
- [x] **Оценка:** 1.5 часа

### S6-003: Output Capture — ✅
- [x] Реализовать перехват stdout (`PrintCollector`)
- [x] Реализовать перехват исключений (тип + сообщение)
- [x] Форматирование вывода
- [x] **Зависит от:** S6-001
- [x] **Оценка:** 1 час

### S6-004: Code Execution Model — ✅
- [x] Создать app/models/code.py (CodeExecution)
- [x] Создать миграцию 002
- [x] Создать схему
- [x] Создать репозиторий
- [x] **Зависит от:** S2-005
- [x] **Оценка:** 1 час

### S6-005: Code API — ✅
- [x] Создать app/api/v1/code.py
- [x] POST /api/v1/code/execute (+ история)
- [x] POST /api/v1/code/analyze
- [x] POST /api/v1/code/lint
- [x] GET /api/v1/code/history, /code/limits
- [x] **Зависит от:** S6-001, S6-003, S6-004
- [x] **Оценка:** 1.5 часа

### S6-006: Python Linter — ✅
- [x] Создать app/core/linter.py
- [ ] Интегрировать pylint или flake8 — не требуется: собственный AST-линтер без лишних зависимостей
- [x] Форматирование ошибок (line/column/code/severity)
- [x] **Зависит от:** S2-001
- [x] **Оценка:** 1 час

### S6-007: Тесты Code Execution — ✅
- [x] tests/test_executor.py (12 тестов: безопасность, вывод, таймаут)
- [x] tests/test_linter.py (13 тестов)
- [x] tests/test_code_api.py (9 тестов)
- [ ] tests/test_executor_memory.py — блокируется KI-009
- [x] **Зависит от:** S6-005, S6-006
- [x] **Оценка:** 1.5 часа

---

## Спринт 7: Task System (День 9)

**Цель:** Реализовать систему задач и прогресса обучения.

### S7-001: Task Model — ✅
- [x] Создать app/models/task.py (Task, UserTaskProgress)
- [x] Создать миграцию 003
- [x] Добавить тестовые данные (seed: `backend/scripts/seed_tasks.py`, 6 задач)
- [x] **Зависит от:** S2-005
- [x] **Оценка:** 1.5 часа

### S7-002: Task Schemas — ✅
- [x] Создать app/schemas/task.py
- [x] Валидация test_cases (минимум 1, максимум 50)
- [x] Валидация hints (максимум 20)
- [x] **Зависит от:** S7-001
- [x] **Оценка:** 1 час

### S7-003: Task Service — ✅
- [x] Создать app/services/task_service.py
- [ ] Генерация задач через LLM (перенесено: сначала ручные задачи)
- [x] Валидация решения (прогон тест-кейсов)
- [x] Подсчёт прогресса
- [x] **Зависит от:** S7-001, S4-001
- [x] **Оценка:** 2 часа

### S7-004: Test Case Runner — ✅
- [x] Создать app/core/test_runner.py
- [x] Запуск тестов для задачи (stdin → input())
- [x] Сравнение результатов (нормализация вывода)
- [x] Форматирование отчёта (по кейсам)
- [x] **Зависит от:** S6-001
- [x] **Оценка:** 1.5 часа

### S7-005: Task API — ✅
- [x] Создать app/api/v1/tasks.py
- [x] GET /api/v1/tasks (фильтры: category, difficulty)
- [x] GET /api/v1/tasks/{id}, /{id}/hints/{index}
- [x] POST /api/v1/tasks/{id}/submit
- [x] GET /api/v1/tasks/progress, /api/v1/tasks/stats
- [x] POST/PATCH/DELETE задач (teacher/admin)
- [x] **Зависит от:** S7-003, S7-004
- [x] **Оценка:** 1.5 часа

### S7-006: Progress Tracking — ✅
- [x] Реализовать подсчёт прогресса пользователя
- [x] Добавить статистику (attempts, completion rate, by difficulty)
- [x] API для статистики
- [x] **Зависит от:** S7-001
- [x] **Оценка:** 1 час

### S7-007: Тесты Task System — ✅
- [x] tests/test_tasks.py (14 тестов: CRUD, submit, прогресс, права)
- [x] tests/test_runner.py (11 тестов: сравнение вывода, stdin, лимиты)
- [x] Проверка эскалации роли при регистрации
- [x] **Зависит от:** S7-005
- [x] **Оценка:** 1.5 часа

---

## Спринт 8: Frontend Base (День 10-11)

**Цель:** Создать базовый React frontend с routing и auth.

### S8-001: React Setup — ✅
- [x] Создать React 19 проект с Vite
- [x] Настроить TypeScript (strict mode, project references)
- [x] Настроить Tailwind CSS 4 (`@tailwindcss/vite`)
- [x] Настроить ESLint (flat config) и Prettier
- [x] **Зависит от:** S1-003
- [x] **Оценка:** 1 час

### S8-002: Project Structure — ✅
- [x] Создать структуру директорий (components, pages, store, lib, i18n, test)
- [x] Настроить алиасы путей (`@/*` в tsconfig и vite)
- [x] Создать базовые типы API (`src/types/api.ts`)
- [x] **Зависит от:** S8-001
- [x] **Оценка:** 1 час

### S8-003: Routing — ✅
- [x] Установить react-router-dom 7
- [x] Создать маршруты (Home, Chat, Tasks, Code, Profile, 404)
- [x] Создать Layout компоненты (AppLayout, header, footer)
- [x] Добавить защищённые маршруты (ProtectedRoute)
- [x] **Зависит от:** S8-002
- [x] **Оценка:** 1.5 часа

### S8-004: API Client — ✅
- [x] Создать src/lib/api.ts (fetch wrapper, ApiError)
- [x] Создать типы для API
- [x] Обработка auth: Bearer-токен, авто-refresh по 401, событие разлогина
- [x] **Зависит от:** S8-002
- [x] **Оценка:** 1 час

### S8-005: State Management — ✅
- [x] Установить Zustand
- [x] Создать стор auth (профиль, вход, регистрация, уровень)
- [ ] Создать сторы chat и tasks (появятся в спринте 9 вместе со страницами)
- [x] Интегрировать с localStorage (токены + кэш профиля)
- [x] **Зависит от:** S8-002
- [x] **Оценка:** 1.5 часа

### S8-006: Authentication Flow — ✅
- [x] Создать страницы Login/Register
- [x] Создать форму входа
- [x] Создать форму регистрации (регистрация → авто-вход)
- [x] Интегрировать с API
- [x] **Зависит от:** S8-003, S8-004, S8-005
- [x] **Оценка:** 2 часа

### S8-007: Basic UI Components — ✅
- [x] Создать компоненты: Button, Input, Card, Alert, Spinner
- [x] Создать Layout: Header, AppLayout, Footer
- [ ] Modal (понадобится в спринте 9)
- [x] Применить Tailwind стили
- [x] **Зависит от:** S8-001
- [x] **Оценка:** 2 часа

### S8-008: i18n Setup — ✅
- [x] Установить react-i18next
- [x] Создать файлы локализации (ru, en)
- [x] Интегрировать в приложение (выбор языка сохраняется в localStorage)
- [x] **Зависит от:** S8-001
- [x] **Оценка:** 1 час

### S8-009: Тесты Frontend — ✅
- [x] Настроить Vitest + jsdom + Testing Library
- [x] Тесты API-клиента (6)
- [x] Тесты стора аутентификации (9)
- [x] Тесты страницы входа (5)
- [ ] Тесты hooks (появятся в спринте 9 с useChat/useWebSocket)
- [x] **Зависит от:** S8-006, S8-007
- [x] **Оценка:** 1.5 часа

### S8-010: Dockerfile фронтенда — ✅ (перенесено из S1-003)
- [x] Multi-stage сборка (node → nginx)
- [x] nginx.conf: SPA-fallback, прокси /api, WebSocket, кэш ассетов
- [x] **Оценка:** 1 час

---

## Спринт 9: Frontend Features (День 12-13)

**Цель:** Реализовать ключевые UI функции (Chat, Code Editor, Tasks).

### S9-001: Chat Interface — ✅
- [x] Создать components/chat/ChatWindow (страница `ChatPage` с сессиями)
- [x] Создать components/chat/MessageList.tsx
- [x] Создать components/chat/MessageInput.tsx
- [x] Создать components/chat/CodeBlock.tsx (+ RichText для markdown-блоков)
- [x] **Зависит от:** S8-007
- [x] **Оценка:** 2.5 часа

### S9-002: WebSocket Integration — ✅
- [x] Создать hooks/useChatSession.ts (+ lib/chatSocket.ts)
- [x] Реализовать соединение с backend (JWT в query)
- [x] Реализовать streaming сообщений (start/token/done/error)
- [x] Обработка ошибок и REST-фолбэк при недоступном WS
- [ ] Авто-reconnect (перенесено: при обрыве следующий запрос уходит в REST)
- [x] **Зависит от:** S9-001, S4-006
- [x] **Оценка:** 2 часа

### S9-003: Level Selector — ✅
- [x] Создать components/chat/LevelSelector.tsx
- [x] Интегрировать с API (уровень задаётся при создании сессии)
- [x] Визуализация текущего уровня (aria-pressed)
- [x] **Зависит от:** S9-001, S5-004
- [x] **Оценка:** 1 час

### S9-004: Code Editor — ✅
- [x] Установить Monaco Editor (`@monaco-editor/react`)
- [x] Создать components/code-editor/CodeEditor.tsx
- [x] Настроить подсветку Python
- [x] Интегрировать с Code API (страница `/code`)
- [ ] Локальный bundle Monaco для офлайн-режима (KI-013)
- [x] **Зависит от:** S8-007
- [x] **Оценка:** 2 часа

### S9-005: Code Execution Panel — ✅
- [x] Создать components/code-editor/OutputPanel.tsx
- [x] Кнопка запуска (на странице `/code`, вместе с линтом)
- [x] Отображение результатов выполнения
- [x] Отображение ошибок и нарушений песочницы
- [x] **Зависит от:** S9-004, S6-005
- [x] **Оценка:** 1.5 часа

### S9-006: Task List — ✅
- [x] Создать страницу `TasksPage` со списком задач (карточки)
- [x] Фильтрация по сложности
- [x] Отображение статуса и числа подсказок
- [x] **Зависит от:** S8-007, S7-005
- [x] **Оценка:** 1.5 часа

### S9-007: Task View — ✅
- [x] Создать pages/TaskDetailPage.tsx
- [x] Отображение описания задачи
- [x] Пошаговые подсказки (по кнопке)
- [x] Интеграция с Code Editor и отправка решения
- [x] Отображение результатов по тест-кейсам
- [x] **Зависит от:** S9-004, S7-005
- [x] **Оценка:** 2 часа

### S9-008: Progress Visualization — ✅
- [x] Полоса прогресса (`role="progressbar"`, completion rate)
- [x] Разбивка по сложности (решено/всего)
- [ ] Отдельная страница статистики (перенесено: блок на странице задач)
- [x] **Зависит от:** S9-006, S7-006
- [x] **Оценка:** 1.5 часа

### S9-009: User Profile — ✅
- [x] Создать pages/ProfilePage.tsx (было в спринте 8)
- [x] Редактирование уровня помощи
- [x] Отображение имени, email и роли
- [ ] Расширенная статистика пользователя (в спринте 10)
- [x] **Зависит от:** S8-007, S3-002
- [x] **Оценка:** 1.5 часа

### S9-010: Тесты Features — ✅
- [x] tests/chat-components.test.tsx (13 тестов)
- [x] tests/code-editor.test.tsx (8 тестов)
- [x] tests/chat-store.test.ts (11 тестов)
- [x] tests/tasks-store.test.ts (8 тестов)
- [ ] tests/hooks/useWebSocket (покрыто через сторы и компоненты)
- [x] **Зависит от:** S9-001..S9-009
- [x] **Оценка:** 2 часа

---

## Спринт 10: Admin & Polish (День 14-15)

**Цель:** Создать админ-панель, финальная документация и деплой.

### S10-001: Admin Dashboard — ✅
- [x] Создать pages/AdminPage.tsx (сводка + пользователи + задачи в одном экране)
- [x] Общая статистика системы (пользователи, задачи, обучение, активность)
- [ ] Графики активности (перенесено: числовые метрики, без графиков)
- [x] **Зависит от:** S8-007
- [x] **Оценка:** 2 часа

### S10-002: Admin Users Management — ✅
- [x] Список пользователей (поиск по имени/email, фильтр по роли)
- [x] Редактирование ролей (select в таблице, API PATCH)
- [ ] Блокировка пользователей (нет поля `is_active`; отложено)
- [x] Запрет понижения/удаления себя
- [x] **Зависит от:** S10-001, S3-003
- [x] **Оценка:** 2 часа

### S10-003: Admin Tasks Management — ⚠️ частично
- [x] Просмотр всех задач, включая неактивные (`GET /admin/tasks`)
- [x] CRUD задач доступен роли `teacher` через `/api/v1/tasks` (без UI-формы)
- [ ] Массовый импорт задач (отложено, seed-скрипт покрывает стартовый набор)
- [x] **Зависит от:** S10-001, S7-005
- [x] **Оценка:** 2 часа

### S10-004: Admin API — ✅
- [x] GET /api/v1/admin/users (+ `role`, `search`, пагинация)
- [x] PATCH /api/v1/admin/users/{id}
- [x] DELETE /api/v1/admin/users/{id}
- [x] GET /api/v1/admin/tasks
- [x] GET /api/v1/admin/analytics
- [ ] POST/PUT/DELETE /admin/tasks (используется `/api/v1/tasks` с ролью teacher)
- [x] **Зависит от:** S3-003, S7-003
- [x] **Оценка:** 2 часа

### S10-005: Analytics Service — ✅
- [x] Создать app/services/analytics_service.py
- [x] Метрики: пользователи по ролям, DAU 24ч/7д, задачи, попытки, completion, активность
- [ ] Экспорт отчётов (CSV/JSON) — отложено
- [x] **Зависит от:** S2-007
- [x] **Оценка:** 1.5 часа

### S10-006: Documentation Finalization — ✅
- [x] Обновить README.md (статус, метрики, навигация)
- [x] Создать docs/README.md, GETTING_STARTED, USER_GUIDE, ARCHITECTURE
- [x] Создать MANUAL_TESTING_GUIDE, ASSISTANT_LEVELS, PROMPT_CURRENT, LLM_EVAL,
      DESIGN_ADMIN_AND_OPS
- [x] Обновить CHANGELOG, RELEASES, KNOWN_ISSUES, RULES, TODO
- [x] **Зависит от:** все предыдущие
- [x] **Оценка:** 2 часа

### S10-007: Production Deployment — ✅
- [x] Создать docker-compose.prod.yml (БД/Redis не публикуются, только frontend)
- [x] Настроить nginx (SPA, /api, WebSocket, кэш ассетов)
- [ ] Настроить SSL (опционально, требует домена — отложено)
- [ ] Настроить мониторинг (метрики в планах, см. DESIGN_ADMIN_AND_OPS §6)
- [x] **Зависит от:** S1-003, S10-006
- [x] **Оценка:** 2 часа

### S10-008: Performance Optimization — ⚠️ частично
- [x] Bundle в пределах лимита: **119 kB gzip** (цель 200 kB)
- [ ] Code splitting по маршрутам (отложено: текущий размер позволяет)
- [ ] Lazy loading тяжёлых страниц (Monaco грузится с CDN)
- [x] Индексы БД для всех фильтров (users, tasks, progress, code, chat)
- [x] **Зависит от:** S9-001..S9-010
- [x] **Оценка:** 2 часа

### S10-009: Final Testing — ⚠️ частично
- [x] Полный прогон: backend 137, frontend 63
- [x] Ручной чек-лист оформлен (MANUAL_TESTING_GUIDE) и пройден в части smoke
- [ ] E2E тесты (Playwright) — KI-012
- [ ] Нагрузочное тестирование — отложено
- [x] **Зависит от:** все предыдущие
- [x] **Оценка:** 2 часа

### S10-010: Release Preparation — ✅
- [x] Версия v0.1.0 в pyproject.toml / package.json
- [x] CHANGELOG: раздел `[0.1.0]` с датой
- [x] Push в GitHub, тег `v0.1.0`
- [ ] GitHub Release: создать вручную на странице релизов
- [x] **Зависит от:** S10-009
- [x] **Оценка:** 1 час

---

## Метрики проекта

### Покрытие кода
- Backend: целевое ≥ 80%
- Frontend: целевое ≥ 60%

### Время выполнения
- Планируемое: 15 дней
- Фактическое: TBD

### Качество кода
- Ruff: 0 ошибок
- Mypy: 0 ошибок
- TypeScript: strict mode

---

## Риски и зависимости

### Риски
1. **LLM API лимиты** — иметь fallback на локальные модели
2. **Code execution security** — тщательное тестирование sandbox
3. **Frontend bundle size** — мониторить размер чанков

### Внешние зависимости
1. DeepSeek API / LM Studio доступность
2. PostgreSQL 17 доступность
3. Redis доступность

---

**Document Status:** Active  
**Last Updated:** 2026-10-29  
**Next Review:** После завершения текущего спринта
