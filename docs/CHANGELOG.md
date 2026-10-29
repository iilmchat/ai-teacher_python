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
- Тесты: 17 (health + auth) на реальном PostgreSQL

### Изменено
- Внешние порты вынесены в ENV: Postgres `5434`, Redis `6381` (KI-001)
- `Settings` читает `.env` из корня проекта по абсолютному пути
- Пароли хэшируются напрямую через `bcrypt` вместо `passlib` (KI-005)

### Исправлено
- Enum-колонки писали имена вместо значений (`STUDENT` вместо `student`) (KI-004)
- `server_default` для JSONB приводил к ошибке миграции
- Конфликт имени `metadata` с `DeclarativeBase` в модели `ChatSession`

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
