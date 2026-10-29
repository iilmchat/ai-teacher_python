# CHANGELOG.md — История версий

Все заметные изменения в проекте документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
и проект следует [Semantic Versioning](https://semver.org/lang/ru/).

---

## [Unreleased]

### Добавлено
- Базовая структура проекта (backend, frontend, docs)
- Документация (Design.md, TODO.md, RULES.md)
- FastAPI-приложение с health check endpoint
- Docker Compose (PostgreSQL 17 + pgvector, Redis)
- CI/CD через GitHub Actions
- Модели данных: `User`, `ChatSession`, `ChatMessage`
- Репозитории с базовым CRUD и специализированными запросами
- Pydantic-схемы для пользователей и чата
- Alembic-миграция `001` (users, chat_sessions, chat_messages, VECTOR)
- JWT-аутентификация: access (30 мин) и refresh (7 дней) токены
- Эндпоинты `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`,
  `GET/PATCH /auth/me`
- RBAC через `require_role` и rate limiting middleware на Redis
- LLM-слой: контракт `LLMProvider`, провайдеры DeepSeek и LM Studio,
  фабрика выбора по `LLM_PROVIDER`
- Промпты трёх уровней в файлах (`prompts/basic|intermediate|advanced.txt`)
- `ChatService`: сессии, история, контекст (20 сообщений), стриминг ответа
- Chat API: `POST/GET /chat/sessions`, `GET/DELETE /chat/sessions/{id}`,
  `POST /chat/sessions/{id}/messages`
- WebSocket `/api/v1/chat/ws/{session_id}` со стримингом `start/token/done/error`
- Управление уровнями: `PATCH /users/me/level`, `GET /users/me/level`,
  `GET /chat/levels`, `GET /users/levels`
- Наследование уровня сессией от профиля + fallback на базовый уровень
- Админские эндпоинты профиля: `GET /users/{id}`, `PATCH /users/{id}/role`
- Доменные ошибки `AppError` с единым HTTP-обработчиком
- Песочница выполнения кода: RestrictedPython, белый список модулей,
  выполнение в отдельном процессе с убийством по таймауту
- AST-линтер: ошибки безопасности, предупреждения стиля, docstring-подсказки
- Code API: `POST /code/execute`, `/code/lint`, `/code/analyze`,
  `GET /code/history`, `/code/limits`
- Модель `CodeExecution` и миграция `002`
- Система задач: модели `Task`/`UserTaskProgress`, миграция `003`, seed из 6 задач
- Проверка решений по тест-кейсам: `stdin` → `input()`, сравнение с нормализацией
- Task API: каталог с фильтрами, карточка, подсказки, submit, CRUD для преподавателей
- Прогресс: `GET /tasks/progress`, `GET /tasks/stats` (попытки, completion rate,
  разбивка по сложности)
- Тесты: 126 (health, auth, chat, prompts, levels, websocket, executor, linter,
  code API, tasks, runner)
- Frontend: React 19 + Vite + TypeScript strict + Tailwind 4
- API-клиент с авто-refresh токена и типизированными ошибками
- Zustand-стор аутентификации, страницы входа и регистрации, профиль с уровнем
- Локализация ru/en, layout с навигацией и защищённые маршруты
- Docker-образ фронтенда (nginx: SPA + прокси `/api` и WebSocket)
- Тесты фронтенда: 20 (Vitest + Testing Library)
- Чат с WebSocket-стримингом и REST-фолбэком, выбор уровня при создании сессии
- Monaco-редактор, страница песочницы с запуском кода и линтом
- Каталог задач с фильтрами, карточка задачи с подсказками и проверкой решения
- Полоса прогресса и разбивка решённых задач по сложности
- Тесты фронтенда: 60 (сторы чата и задач, компоненты, редактор)

### Изменено
- Навигация ведёт на реальные страницы вместо заглушек; неизвестный путь → `/404`

### Безопасность
- Регистрация больше не принимает `role`: эскалация до admin/teacher закрыта (KI-011)

### Изменено
- Внешние порты вынесены в ENV: Postgres `5434`, Redis `6381` (KI-001)
- `Settings` читает `.env` из корня проекта по абсолютному пути
- Пароли хэшируются напрямую через `bcrypt` вместо `passlib` (KI-005)
- Healthcheck возвращает `llm_provider`
- `ChatSessionCreate.level` необязателен: сессия наследует уровень профиля

### Исправлено
- Enum-колонки писали имена вместо значений (`STUDENT` вместо `student`) (KI-004)
- `server_default` для JSONB приводил к ошибке миграции
- Конфликт имени `metadata` с `DeclarativeBase` в модели `ChatSession`
- Дефолт `level="basic"` в запросе перебивал уровень профиля пользователя

### Безопасность
- bcrypt-хэширование паролей, ограничение длины 72 байтами
- Rate limiting: 5 запросов/мин на login, 300/мин общий лимит
- JWT-токены разделены по типу (`access` / `refresh`)

---

## [0.1.0] - 2026-10-29

### Добавлено
- Базовая архитектура проекта
- Документация по разработке
- Структура backend и frontend

---

## Типы изменений

- `Добавлено` — новые функции
- `Изменено` — изменения в существующих функциях
- `Устарело` — функции, которые будут удалены
- `Удалено` — удалённые функции
- `Исправлено` — исправления багов
- `Безопасность` — исправления уязвимостей
