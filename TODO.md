# TODO.md — AI Teacher for Python

> Этот документ — план разработки проекта. Каждая задача имеет ID, зависимости и статус.
> Статусы: `[ ]` — не начато, `[~]` — в работе, `[x]` — завершено, `[!]` — блокер (см. KNOWN_ISSUES.md)

**Версия:** v0.1.0  
**Последнее обновление:** 2026-10-29  
**Текущий спринт:** Спринт 1

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

### S1-001: Создание структуры директорий
- [ ] Создать корневую структуру проекта
- [ ] Создать директории backend/app/*, frontend/src/*, docs/*
- [ ] Создать пустые __init__.py файлы
- [ ] Создать .gitignore для Python и Node.js
- [ ] **Зависит от:** нет
- [ ] **Оценка:** 30 мин

### S1-002: Настройка Python окружения
- [ ] Создать pyproject.toml с зависимостями (FastAPI, SQLAlchemy, Pydantic, etc.)
- [ ] Создать requirements.txt для Docker
- [ ] Настроить ruff и mypy конфигурацию
- [ ] Создать .python-version для pyenv
- [ ] **Зависит от:** S1-001
- [ ] **Оценка:** 30 мин

### S1-003: Docker Compose конфигурация
- [ ] Создать docker-compose.yml (PostgreSQL, Redis, backend, frontend)
- [ ] Создать .env.example с переменными окружения
- [ ] Создать Dockerfile для backend
- [ ] Создать Dockerfile для frontend
- [ ] Протестировать docker compose up
- [ ] **Зависит от:** S1-002
- [ ] **Оценка:** 1 час

### S1-004: Git и CI/CD
- [ ] Инициализировать git репозиторий
- [ ] Создать ветку main
- [ ] Создать .github/workflows/ci.yml (lint, test, build)
- [ ] Создать .github/workflows/deploy.yml (опционально)
- [ ] Создать первый коммит
- [ ] **Зависит от:** S1-001, S1-002, S1-003
- [ ] **Оценка:** 1 час

### S1-005: Документация
- [ ] Создать README.md с описанием проекта
- [ ] Создать docs/RULES.md (адаптировать из ai-chess-annotator)
- [ ] Создать docs/KNOWN_ISSUES.md (пустой шаблон)
- [ ] Создать docs/CHANGELOG.md (инициализация)
- [ ] **Зависит от:** S1-001
- [ ] **Оценка:** 30 мин

### S1-006: Pre-commit hooks
- [ ] Настроить Husky или pre-commit
- [ ] Добавить хуки: ruff, mypy, prettier
- [ ] Добавить проверку секретов (detect-secrets)
- [ ] **Зависит от:** S1-002
- [ ] **Оценка:** 30 мин

---

## Спринт 2: Backend Core (День 2-3)

**Цель:** Создать базовый FastAPI проект с подключением к PostgreSQL и Redis.

### S2-001: FastAPI приложение
- [ ] Создать app/main.py с FastAPI приложением
- [ ] Создать app/config.py с настройками (pydantic-settings)
- [ ] Создать app/dependencies.py для DI
- [ ] Добавить healthcheck эндпоинт
- [ ] Добавить CORS middleware
- [ ] **Зависит от:** S1-002
- [ ] **Оценка:** 1 час

### S2-002: PostgreSQL + SQLAlchemy
- [ ] Создать app/db/database.py (async engine)
- [ ] Создать app/db/session.py (async session maker)
- [ ] Создать базовую модель с UUID и timestamps
- [ ] Настроить пул соединений
- [ ] **Зависит от:** S2-001
- [ ] **Оценка:** 1.5 часа

### S2-003: Redis подключение
- [ ] Создать app/db/redis.py (async redis client)
- [ ] Добавить healthcheck для Redis
- [ ] Создать утилиты для кэширования
- [ ] **Зависит от:** S2-001
- [ ] **Оценка:** 1 час

### S2-004: Alembic миграции
- [ ] Инициализировать Alembic
- [ ] Создать начальную миграцию (пустую)
- [ ] Протестировать upgrade/downgrade
- [ ] **Зависит от:** S2-002
- [ ] **Оценка:** 1 час

### S2-005: Модели данных (User, ChatSession, ChatMessage)
- [ ] Создать app/models/user.py
- [ ] Создать app/models/chat.py
- [ ] Создать миграцию для моделей
- [ ] Добавить индексы
- [ ] **Зависит от:** S2-002, S2-004
- [ ] **Оценка:** 2 часа

### S2-006: Pydantic схемы
- [ ] Создать app/schemas/user.py
- [ ] Создать app/schemas/chat.py
- [ ] Добавить валидацию
- [ ] **Зависит от:** S2-005
- [ ] **Оценка:** 1 час

### S2-007: Репозитории
- [ ] Создать app/db/repositories/base.py (BaseRepository)
- [ ] Создать app/db/repositories/user.py
- [ ] Создать app/db/repositories/chat.py
- [ ] **Зависит от:** S2-005, S2-006
- [ ] **Оценка:** 1.5 часа

### S2-008: Тесты Backend Core
- [ ] Создать tests/conftest.py (fixtures)
- [ ] Создать tests/test_health.py
- [ ] Создать tests/test_db.py
- [ ] Настроить pytest-asyncio
- [ ] **Зависит от:** S2-001, S2-002, S2-003
- [ ] **Оценка:** 1 час

---

## Спринт 3: Authentication (День 4)

**Цель:** Реализовать JWT аутентификацию с ролями.

### S3-001: Security модуль
- [ ] Создать app/core/security.py
- [ ] Реализовать хэширование паролей (bcrypt)
- [ ] Реализовать JWT токены (access + refresh)
- [ ] Реализовать валидацию токенов
- [ ] **Зависит от:** S2-001
- [ ] **Оценка:** 1.5 часа

### S3-002: Auth API endpoints
- [ ] Создать app/api/v1/auth.py
- [ ] POST /api/v1/auth/register
- [ ] POST /api/v1/auth/login
- [ ] POST /api/v1/auth/logout
- [ ] POST /api/v1/auth/refresh
- [ ] GET /api/v1/auth/me
- [ ] **Зависит от:** S3-001, S2-006
- [ ] **Оценка:** 2 часа

### S3-003: Role-Based Access Control (RBAC)
- [ ] Добавить роли в модель User (student, teacher, admin)
- [ ] Создать декоратор require_role
- [ ] Создать middleware для проверки токена
- [ ] Добавить проверки в endpoints
- [ ] **Зависит от:** S3-001, S2-005
- [ ] **Оценка:** 1.5 часа

### S3-004: Rate Limiting
- [ ] Создать app/core/rate_limiter.py
- [ ] Настроить лимиты: login (5/мин), общий (300/мин)
- [ ] Интегрировать с Redis
- [ ] Добавить middleware
- [ ] **Зависит от:** S2-003
- [ ] **Оценка:** 1 час

### S3-005: Тесты Authentication
- [ ] tests/test_auth_register.py
- [ ] tests/test_auth_login.py
- [ ] tests/test_auth_rbac.py
- [ ] tests/test_rate_limiter.py
- [ ] **Зависит от:** S3-002, S3-003, S3-004
- [ ] **Оценка:** 1.5 часа

---

## Спринт 4: Chat Service (День 5-6)

**Цель:** Реализовать чат-сервис с интеграцией LLM.

### S4-001: LLM Provider Interface
- [ ] Создать app/services/llm/base.py (абстрактный класс)
- [ ] Создать app/services/llm/deepseek.py
- [ ] Создать app/services/llm/lm_studio.py
- [ ] Добавить конфигурацию провайдеров
- [ ] **Зависит от:** S2-001, S2-002
- [ ] **Оценка:** 2 часа

### S4-002: Chat Service
- [ ] Создать app/services/chat_service.py
- [ ] Реализовать создание сессии
- [ ] Реализовать отправку сообщения
- [ ] Реализовать получение истории
- [ ] **Зависит от:** S2-007, S4-001
- [ ] **Оценка:** 2 часа

### S4-003: Prompt Management
- [ ] Создать app/services/llm/prompts/ директорию
- [ ] Создать базовый промпт
- [ ] Создать систему подстановки переменных
- [ ] Добавить версию промптов
- [ ] **Зависит от:** S4-001
- [ ] **Оценка:** 1.5 часа

### S4-004: Context Management
- [ ] Реализовать сбор контекста из истории чата
- [ ] Добавить truncation для длинных диалогов
- [ ] Добавить injection системного промпта
- [ ] **Зависит от:** S4-002
- [ ] **Оценка:** 1 час

### S4-005: Chat API
- [ ] Создать app/api/v1/chat.py
- [ ] POST /api/v1/chat/sessions
- [ ] GET /api/v1/chat/sessions
- [ ] GET /api/v1/chat/sessions/{id}
- [ ] DELETE /api/v1/chat/sessions/{id}
- [ ] POST /api/v1/chat/sessions/{id}/messages
- [ ] **Зависит от:** S4-002, S2-006
- [ ] **Оценка:** 2 часа

### S4-006: WebSocket для чата
- [ ] Создать app/api/websocket.py
- [ ] Реализовать streaming ответов LLM
- [ ] Добавить heartbeat
- [ ] Добавить error handling
- [ ] **Зависит от:** S4-005
- [ ] **Оценка:** 2 часа

### S4-007: Тесты Chat Service
- [ ] tests/test_chat_sessions.py
- [ ] tests/test_chat_messages.py
- [ ] tests/test_llm_providers.py (mock)
- [ ] tests/test_websocket.py
- [ ] **Зависит от:** S4-005, S4-006
- [ ] **Оценка:** 2 часа

---

## Спринт 5: Three Levels (День 7)

**Цель:** Реализовать три уровня ассистента с разными промптами.

### S5-001: Level-specific Prompts
- [ ] Создать app/services/llm/prompts/basic.txt
- [ ] Создать app/services/llm/prompts/intermediate.txt
- [ ] Создать app/services/llm/prompts/advanced.txt
- [ ] Протестировать каждый уровень вручную
- [ ] **Зависит от:** S4-003
- [ ] **Оценка:** 2 часа

### S5-002: Level Management
- [ ] Добавить поле level в User и ChatSession
- [ ] Реализовать переключение уровня
- [ ] Добавить валидацию уровня
- [ ] Обновить схемы
- [ ] **Зависит от:** S2-005, S4-002
- [ ] **Оценка:** 1 час

### S5-003: Level-aware Response Generation
- [ ] Интегрировать выбор промпта в ChatService
- [ ] Добавить метаданные уровня в ответ
- [ ] Реализовать fallback логику
- [ ] **Зависит от:** S5-001, S5-002
- [ ] **Оценка:** 1.5 часа

### S5-004: Level API
- [ ] PATCH /api/v1/users/me/level
- [ ] GET /api/v1/chat/levels (информация о уровнях)
- [ ] Обновить POST /api/v1/chat/sessions (параметр level)
- [ ] **Зависит от:** S5-002
- [ ] **Оценка:** 1 час

### S5-005: Тесты Levels
- [ ] tests/test_levels_basic.py
- [ ] tests/test_levels_intermediate.py
- [ ] tests/test_levels_advanced.py
- [ ] tests/test_level_switching.py
- [ ] **Зависит от:** S5-003, S5-004
- [ ] **Оценка:** 1.5 часа

---

## Спринт 6: Code Execution (День 8)

**Цель:** Реализовать безопасное выполнение Python кода.

### S6-001: Sandboxed Executor
- [ ] Создать app/core/executor.py
- [ ] Интегрировать RestrictedPython
- [ ] Реализовать timeout (5 сек)
- [ ] Реализовать memory limit (128 MB)
- [ ] **Зависит от:** S2-001
- [ ] **Оценка:** 2.5 часа

### S6-002: Safe Builtins
- [ ] Создать whitelist разрешённых модулей
- [ ] Создать whitelist разрешённых функций
- [ ] Заблокировать опасные операции (os, sys, subprocess)
- [ ] Добавить логирование попыток нарушения
- [ ] **Зависит от:** S6-001
- [ ] **Оценка:** 1.5 часа

### S6-003: Output Capture
- [ ] Реализовать перехват stdout/stderr
- [ ] Реализовать перехват исключений
- [ ] Форматирование вывода
- [ ] **Зависит от:** S6-001
- [ ] **Оценка:** 1 час

### S6-004: Code Execution Model
- [ ] Создать app/models/code.py (CodeExecution)
- [ ] Создать миграцию
- [ ] Создать схему
- [ ] Создать репозиторий
- [ ] **Зависит от:** S2-005
- [ ] **Оценка:** 1 час

### S6-005: Code API
- [ ] Создать app/api/v1/code.py
- [ ] POST /api/v1/code/execute
- [ ] POST /api/v1/code/analyze
- [ ] POST /api/v1/code/lint
- [ ] **Зависит от:** S6-001, S6-003, S6-004
- [ ] **Оценка:** 1.5 часа

### S6-006: Python Linter
- [ ] Создать app/core/linter.py
- [ ] Интегрировать pylint или flake8
- [ ] Форматирование ошибок
- [ ] **Зависит от:** S2-001
- [ ] **Оценка:** 1 час

### S6-007: Тесты Code Execution
- [ ] tests/test_executor_safe.py
- [ ] tests/test_executor_timeout.py
- [ ] tests/test_executor_memory.py
- [ ] tests/test_linter.py
- [ ] **Зависит от:** S6-005, S6-006
- [ ] **Оценка:** 1.5 часа

---

## Спринт 7: Task System (День 9)

**Цель:** Реализовать систему задач и прогресса обучения.

### S7-001: Task Model
- [ ] Создать app/models/task.py (Task, UserTaskProgress)
- [ ] Создать миграцию
- [ ] Добавить тестовые данные (seed)
- [ ] **Зависит от:** S2-005
- [ ] **Оценка:** 1.5 часа

### S7-002: Task Schemas
- [ ] Создать app/schemas/task.py
- [ ] Валидация test_cases
- [ ] Валидация hints
- [ ] **Зависит от:** S7-001
- [ ] **Оценка:** 1 час

### S7-003: Task Service
- [ ] Создать app/services/task_service.py
- [ ] Генерация задач (опционально через LLM)
- [ ] Валидация решения
- [ ] Подсчёт прогресса
- [ ] **Зависит от:** S7-001, S4-001
- [ ] **Оценка:** 2 часа

### S7-004: Test Case Runner
- [ ] Создать app/core/test_runner.py
- [ ] Запуск тестов для задачи
- [ ] Сравнение результатов
- [ ] Форматирование отчёта
- [ ] **Зависит от:** S6-001
- [ ] **Оценка:** 1.5 часа

### S7-005: Task API
- [ ] Создать app/api/v1/tasks.py
- [ ] GET /api/v1/tasks (фильтры: category, difficulty)
- [ ] GET /api/v1/tasks/{id}
- [ ] POST /api/v1/tasks/{id}/submit
- [ ] GET /api/v1/tasks/progress
- [ ] **Зависит от:** S7-003, S7-004
- [ ] **Оценка:** 1.5 часа

### S7-006: Progress Tracking
- [ ] Реализовать подсчёт прогресса пользователя
- [ ] Добавить статистику ( attempts, completion rate)
- [ ] API для статистики
- [ ] **Зависит от:** S7-001
- [ ] **Оценка:** 1 час

### S7-007: Тесты Task System
- [ ] tests/test_task_crud.py
- [ ] tests/test_task_submit.py
- [ ] tests/test_progress.py
- [ ] tests/test_test_runner.py
- [ ] **Зависит от:** S7-005
- [ ] **Оценка:** 1.5 часа

---

## Спринт 8: Frontend Base (День 10-11)

**Цель:** Создать базовый React frontend с routing и auth.

### S8-001: React Setup
- [ ] Создать React 19 проект с Vite
- [ ] Настроить TypeScript (strict mode)
- [ ] Настроить Tailwind CSS 4
- [ ] Настроить ESLint и Prettier
- [ ] **Зависит от:** S1-003
- [ ] **Оценка:** 1 час

### S8-002: Project Structure
- [ ] Создать структуру директорий (components, pages, hooks, etc.)
- [ ] Настроить алиасы путей (@/components)
- [ ] Создать базовые типы
- [ ] **Зависит от:** S8-001
- [ ] **Оценка:** 1 час

### S8-003: Routing
- [ ] Установить react-router-dom 7
- [ ] Создать маршруты (Home, Chat, Tasks, Profile)
- [ ] Создать Layout компоненты
- [ ] Добавить защищённые маршруты
- [ ] **Зависит от:** S8-002
- [ ] **Оценка:** 1.5 часа

### S8-004: API Client
- [ ] Создать src/lib/api.ts (fetch wrapper)
- [ ] Создать типы для API
- [ ] Добавить interceptors (auth, error handling)
- [ ] **Зависит от:** S8-002
- [ ] **Оценка:** 1 час

### S8-005: State Management
- [ ] Установить Zustand
- [ ] Создать stores (auth, chat, tasks)
- [ ] Интегрировать с localStorage (auth)
- [ ] **Зависит от:** S8-002
- [ ] **Оценка:** 1.5 часа

### S8-006: Authentication Flow
- [ ] Создать страницы Login/Register
- [ ] Создать форму входа
- [ ] Создать форму регистрации
- [ ] Интегрировать с API
- [ ] **Зависит от:** S8-003, S8-004, S8-005
- [ ] **Оценка:** 2 часа

### S8-007: Basic UI Components
- [ ] Создать компоненты: Button, Input, Card, Modal
- [ ] Создать Layout: Header, Sidebar, Footer
- [ ] Применить Tailwind стили
- [ ] **Зависит от:** S8-001
- [ ] **Оценка:** 2 часа

### S8-008: i18n Setup
- [ ] Установить react-i18next
- [ ] Создать файлы локализации (ru, en)
- [ ] Интегрировать в приложение
- [ ] **Зависит от:** S8-001
- [ ] **Оценка:** 1 час

### S8-009: Тесты Frontend
- [ ] Настроить Vitest
- [ ] Создать тесты для компонентов
- [ ] Создать тесты для hooks
- [ ] **Зависит от:** S8-006, S8-007
- [ ] **Оценка:** 1.5 часа

---

## Спринт 9: Frontend Features (День 12-13)

**Цель:** Реализовать ключевые UI функции (Chat, Code Editor, Tasks).

### S9-001: Chat Interface
- [ ] Создать components/Chat/ChatWindow.tsx
- [ ] Создать components/Chat/MessageList.tsx
- [ ] Создать components/Chat/MessageInput.tsx
- [ ] Создать components/Chat/CodeBlock.tsx
- [ ] **Зависит от:** S8-007
- [ ] **Оценка:** 2.5 часа

### S9-002: WebSocket Integration
- [ ] Создать hooks/useWebSocket.ts
- [ ] Реализовать соединение с backend
- [ ] Реализовать streaming сообщений
- [ ] Обработка ошибок и reconnect
- [ ] **Зависит от:** S9-001, S4-006
- [ ] **Оценка:** 2 часа

### S9-003: Level Selector
- [ ] Создать components/Chat/LevelSelector.tsx
- [ ] Интегрировать с API
- [ ] Визуализация текущего уровня
- [ ] **Зависит от:** S9-001, S5-004
- [ ] **Оценка:** 1 час

### S9-004: Code Editor
- [ ] Установить Monaco Editor
- [ ] Создать components/CodeEditor/Editor.tsx
- [ ] Настроить подсветку Python
- [ ] Интегрировать с Code API
- [ ] **Зависит от:** S8-007
- [ ] **Оценка:** 2 часа

### S9-005: Code Execution Panel
- [ ] Создать components/CodeEditor/OutputPanel.tsx
- [ ] Создать components/CodeEditor/RunButton.tsx
- [ ] Отображение результатов выполнения
- [ ] Отображение ошибок
- [ ] **Зависит от:** S9-004, S6-005
- [ ] **Оценка:** 1.5 часа

### S9-006: Task List
- [ ] Создать components/Tasks/TaskList.tsx
- [ ] Создать components/Tasks/TaskCard.tsx
- [ ] Фильтрация по категории и сложности
- [ ] **Зависит от:** S8-007, S7-005
- [ ] **Оценка:** 1.5 часа

### S9-007: Task View
- [ ] Создать components/Tasks/TaskView.tsx
- [ ] Отображение описания задачи
- [ ] Интеграция с Code Editor
- [ ] Отправка решения
- [ ] **Зависит от:** S9-004, S7-005
- [ ] **Оценка:** 2 часа

### S9-008: Progress Visualization
- [ ] Создать components/Tasks/ProgressBar.tsx
- [ ] Создать components/Progress/Stats.tsx
- [ ] Графики прогресса
- [ ] **Зависит от:** S9-006, S7-006
- [ ] **Оценка:** 1.5 часа

### S9-009: User Profile
- [ ] Создать pages/Profile.tsx
- [ ] Редактирование настроек
- [ ] Смена уровня
- [ ] Статистика пользователя
- [ ] **Зависит от:** S8-007, S3-002
- [ ] **Оценка:** 1.5 часа

### S9-010: Тесты Features
- [ ] tests/components/Chat.test.tsx
- [ ] tests/components/CodeEditor.test.tsx
- [ ] tests/components/Tasks.test.tsx
- [ ] tests/hooks/useWebSocket.test.ts
- [ ] **Зависит от:** S9-001..S9-009
- [ ] **Оценка:** 2 часа

---

## Спринт 10: Admin & Polish (День 14-15)

**Цель:** Создать админ-панель, финальная документация и деплой.

### S10-001: Admin Dashboard
- [ ] Создать pages/Admin/Dashboard.tsx
- [ ] Общая статистика системы
- [ ] Графики активности
- [ ] **Зависит от:** S8-007
- [ ] **Оценка:** 2 часа

### S10-002: Admin Users Management
- [ ] Создать pages/Admin/Users.tsx
- [ ] Список пользователей
- [ ] Редактирование ролей
- [ ] Блокировка пользователей
- [ ] **Зависит от:** S10-001, S3-003
- [ ] **Оценка:** 2 часа

### S10-003: Admin Tasks Management
- [ ] Создать pages/Admin/Tasks.tsx
- [ ] CRUD для задач
- [ ] Массовый импорт задач
- [ ] **Зависит от:** S10-001, S7-005
- [ ] **Оценка:** 2 часа

### S10-004: Admin API
- [ ] GET /api/v1/admin/users
- [ ] PATCH /api/v1/admin/users/{id}
- [ ] DELETE /api/v1/admin/users/{id}
- [ ] POST /api/v1/admin/tasks
- [ ] PUT /api/v1/admin/tasks/{id}
- [ ] DELETE /api/v1/admin/tasks/{id}
- [ ] GET /api/v1/admin/analytics
- [ ] **Зависит от:** S3-003, S7-003
- [ ] **Оценка:** 2 часа

### S10-005: Analytics Service
- [ ] Создать app/services/analytics_service.py
- [ ] Подсчёт метрик (DAU, MAU, completion rate)
- [ ] Экспорт отчётов
- [ ] **Зависит от:** S2-007
- [ ] **Оценка:** 1.5 часа

### S10-006: Documentation Finalization
- [ ] Обновить README.md
- [ ] Создать docs/GETTING_STARTED.md
- [ ] Создать docs/USER_GUIDE.md
- [ ] Создать docs/ARCHITECTURE.md
- [ ] Обновить docs/CHANGELOG.md
- [ ] **Зависит от:** все предыдущие
- [ ] **Оценка:** 2 часа

### S10-007: Production Deployment
- [ ] Создать docker-compose.prod.yml
- [ ] Настроить nginx
- [ ] Настроить SSL (опционально)
- [ ] Настроить мониторинг
- [ ] **Зависит от:** S1-003, S10-006
- [ ] **Оценка:** 2 часа

### S10-008: Performance Optimization
- [ ] Оптимизация frontend bundle
- [ ] Code splitting
- [ ] Lazy loading
- [ ] Оптимизация SQL запросов
- [ ] **Зависит от:** S9-001..S9-010
- [ ] **Оценка:** 2 часа

### S10-009: Final Testing
- [ ] Полный прогон всех тестов
- [ ] E2E тесты (Playwright)
- [ ] Нагрузочное тестирование (опционально)
- [ ] **Зависит от:** все предыдущие
- [ ] **Оценка:** 2 часа

### S10-010: Release Preparation
- [ ] Создать GitHub release
- [ ] Обновить версию в pyproject.toml
- [ ] Обновить CHANGELOG.md
- [ ] Push в GitHub
- [ ] **Зависит от:** S10-009
- [ ] **Оценка:** 1 час

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
