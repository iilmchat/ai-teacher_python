# RELEASES.md — Журнал спринтов

> Этот документ содержит историю всех спринтов и релизов проекта.

**Текущая версия:** v0.1.0  
**Текущий спринт:** Спринт 4 (Chat Service)

---

## Оглавление

- [Спринт 1: Project Setup](#спринт-1-project-setup)
- [Спринт 2: Backend Core](#спринт-2-backend-core)
- [Спринт 3: Authentication](#спринт-3-authentication)
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
