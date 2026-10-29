# CHANGELOG.md — История версий

Все заметные изменения в проекте документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
и проект следует [Semantic Versioning](https://semver.org/lang/ru/).

---

## [Unreleased]

### Добавлено
- Кабинет учителя: `/teacher/tasks` (CRUD, тест-кейсы, импорт с предпросмотром)
  и `/teacher/students` (агрегаты и прогресс по задачам)
- API учителя: `/teacher/tasks`, `/teacher/students`,
  `/teacher/students/{id}/progress`; импорт файла `/tasks/import/file`
- Локальный Monaco без CDN: ассеты `public/monaco/vs`, lazy-чанк,
  `pnpm test:offline` (KI-013)
- Code splitting всех маршрутов: entry 76.3 kB gzip, vendor-чанки
- Импорт/экспорт задач: JSON и YAML, `POST /tasks/import`,
  `GET /tasks/export?format=json|yaml`, CLI `scripts/import_tasks.py`
- `SEED_ON_START=true` — идемпотентное наполнение задач при старте (KI-010)
- Генерация задач через LLM: `POST /tasks/generate`, проверка эталонного
  решения в песочнице, отчёт `created/rejected`
- Теги задач (`tasks.tags`, GIN-индекс) и поиск `?tag=&q=`,
  `GET /tasks/categories`
- История версий задач (`task_versions`), `GET /tasks/{id}/versions` и откат
- Живой прогон LLM_EVAL на DeepSeek: 15 ответов, оценки basic 0.99 /
  intermediate 0.93 / advanced 0.96; отчёт `docs/reports/llm-eval/2026-10-29/`
- `LM_STUDIO_MODEL` — имя локальной модели; `qwen/qwen3-4b-2507` проверен
  как fallback на `127.0.0.1:8034`
- Лимит памяти песочницы в дочернем процессе: `RLIMIT_AS` на POSIX,
  Job Object на Windows; `EXECUTOR_MEMORY_LIMIT` подхватывается (KI-009)
- Ограничение одновременных запусков: `EXECUTOR_MAX_CONCURRENCY`,
  `EXECUTOR_QUEUE_TIMEOUT`, 503 при перегрузке
- Обрезка вывода `EXECUTOR_MAX_OUTPUT` с пометкой `output_truncated`
- 14 тестов-атак: сеть, файлы, `__builtins__`, `getattr`, dunder
- Healthcheck LLM в `/api/v1/health`: статус `ok` / `degraded` / `not_configured`,
  провайдер, модель, fallback; ping с кэшем 60 с, ключ не раскрывается
- Fallback провайдеров: `LLM_FALLBACK_PROVIDER`, один повтор, 503 при отказе обоих
- Метрики LLM в памяти процесса: запросы, ошибки, latency, первый токен, токены;
  секция `llm` в `/admin/analytics` и карточка в админке
- Детектор «готового решения» для базового уровня: `warnings` в REST/WS,
  лог `level_policy_warning`
- Версии промптов (`prompts/versions.json`) и метаданные ответа
  (`provider`, `model`, `prompt_version`, `warnings`) в истории чата
- Миграция 004: `chat_messages.metadata` JSONB
- Инструмент прогона LLM_EVAL: `scripts/run_llm_eval.py` (Q1–Q5 × 3 уровня)
- E2E-тесты Playwright (12 сценариев): auth, чат, песочница, задачи, запрет админки
- Детерминированный LLM-провайдер `echo` для e2e и демо без ключа (`LLM_PROVIDER=echo`)
- Rate limiting в рантайме: Redis-клиент, middleware, 429 + `Retry-After`, fail-open
- Интеграционные тесты WebSocket-стриминга (протокол `start/token/done`)
- Тесты миграций Alembic: upgrade на пустую БД, сверка с моделями, downgrade→upgrade
- Скрипт `scripts/check_ports.py` — проверка портов и «своей» БД
- Пороги покрытия: backend 70% (факт 81), frontend 70/60/70 (факт 74/78/84)
- Job `e2e` в CI (Playwright + отдельная БД)

### Исправлено
- После перезагрузки страницы защищённые маршруты висели на Spinner:
  `loadMe()` теперь вызывается при старте приложения

### Изменено
- WS-протокол вынесен в `serve_chat_socket`; эндпоинт получает сессию и
  провайдера через `Depends` (тестируемость)
- `pytest`-маркеры `slow` и `migrations`; полный backend-прогон ~59 с
- WS-сообщение `done` содержит `warnings` политики уровня
- `/code/limits` отдаёт лимиты памяти, вывода и параллелизма; результат
  выполнения — `memory_limit_enforced` / `output_truncated`
- Задачи: `tags` в ответах API, `q`/`tag` в каталоге, `PyYAML` в зависимостях
- Frontend: `@monaco-editor/react` удалён, используется `monaco-editor` с
  локальными AMD-ассетами и `MonacoEditor` lazy-чанком

### Исправлено
- Лимит памяти песочницы на Windows больше не «декоративный»: Job Object
  реально ограничивает committed memory (KI-009)
- Промпт среднего уровня: примеры — на других данных, при просьбе «напиши
  программу» — только каркас и шаги; версия промпта intermediate = 2
  (по итогам живого прогона, KI-008)

### Не сделано
- Живой прогон LLM_EVAL (KI-008 Blocked: нет `DEEPSEEK_API_KEY`, LM Studio не запущен)

---

## [0.1.0] - 2026-10-29

Первый релиз: backend, frontend, админка, документация.

### Добавлено

**Инфраструктура**
- Структура проекта (`backend/`, `frontend/`, `docs/`), `Docker Compose`, CI GitHub Actions
- Документация: `Design.md`, `TODO.md`, `docs/RULES.md` и 15 документов в `docs/`

**Backend**
- FastAPI-приложение с health-check и структурированными логами (`structlog`)
- Модели `User`, `ChatSession`, `ChatMessage`, `CodeExecution`, `Task`, `UserTaskProgress`
- Alembic-миграции `001`–`003` (pgvector, JSONB, enum-типы)
- Репозитории с CRUD и специализированными запросами; Pydantic-схемы
- JWT-аутентификация (access 30 мин, refresh 7 дней), bcrypt, RBAC
- Эндпоинты `/auth/*`, `/users/*`, `/chat/*`, `/code/*`, `/tasks/*`, `/admin/*`
- LLM-слой: контракт `LLMProvider`, провайдеры DeepSeek и LM Studio, фабрика
- Промпты трёх уровней в файлах (`basic`, `intermediate`, `advanced`)
- Чат: сессии, история, контекст (20 сообщений), стриминг, WebSocket
- Песочница кода: AST-проверки, RestrictedPython, белый список модулей,
  изоляция процесса с убийством по таймауту, `stdin` для `input()`
- Линтер: ошибки безопасности, предупреждения стиля, подсказки, метрики
- Система задач: проверка по тест-кейсам, подсказки, прогресс, статистика
- Аналитика для админки: пользователи по ролям, DAU, задачи, попытки, активность
- Доменные ошибки `AppError` с единым HTTP-обработчиком

**Frontend**
- React 19 + Vite 6 + TypeScript strict + Tailwind 4 + ESLint/Prettier
- API-клиент с авто-refresh токена, `ApiError`, обработка ошибок Pydantic
- Zustand-сторы: `auth`, `chat`, `tasks`
- Страницы: главная, вход, регистрация, профиль, чат, песочница, задачи,
  детали задачи, админка, 404
- Чат со стримингом (WebSocket) и REST-фолбэком; блоки кода с копированием
- Monaco-редактор, панель вывода с результатом, ошибками, нарушениями, линтом
- Каталог задач с фильтрами, подсказки по одной, отчёт по тест-кейсам
- Прогресс: полоса и разбивка по сложности
- Админка: дашборд, поиск и таблица пользователей, смена ролей, список задач
- i18n ru/en, Docker-образ (node → nginx) с SPA-fallback и прокси `/api`+WS

**Тесты**
- Backend: **137** (pytest, реальный PostgreSQL, транзакционный откат)
- Frontend: **63** (Vitest + Testing Library)

### Изменено
- Внешние порты вынесены в ENV: Postgres `5434`, Redis `6381` (KI-001)
- `Settings` читает `.env` из корня проекта по абсолютному пути
- Пароли хэшируются напрямую через `bcrypt` вместо `passlib` (KI-005)
- Healthcheck возвращает `llm_provider`
- `ChatSessionCreate.level` необязателен: сессия наследует уровень профиля
- Навигация ведёт на реальные страницы; неизвестный путь → `/404`

### Исправлено
- Enum-колонки писали имена вместо значений (`STUDENT` вместо `student`) (KI-004)
- `server_default` для JSONB приводил к ошибке миграции
- Конфликт имени `metadata` с `DeclarativeBase` в модели `ChatSession`
- Дефолт `level="basic"` в запросе перебивал уровень профиля пользователя
- `app/models/__init__.py` не импортировал модели — Alembic не видел таблиц
- Lazy-relationship `task.progress` давал `MissingGreenlet` в async-сессии
- `.gitignore` с `lib/` игнорировал `frontend/src/lib/**`

### Безопасность
- Регистрация не принимает `role`: эскалация до admin/teacher закрыта (KI-011)
- bcrypt-хэширование паролей, ограничение длины 72 байтами
- JWT-токены разделены по типу (`access` / `refresh`)
- Rate limiting реализован (5/мин на login, 300/мин общий) — не подключён (KI-007)
- Песочница: запрет `os`/`sys`/`subprocess`/`open`/`eval`/`exec`, dunder-атрибутов
- Чужие ресурсы (чаты, история запусков, задачи) недоступны — 403
- Админ не может понизить или удалить сам себя

---

## Типы изменений

- `Добавлено` — новые функции
- `Изменено` — изменения в существующих функциях
- `Устарело` — функции, которые будут удалены
- `Удалено` — удалённые функции
- `Исправлено` — исправления багов
- `Безопасность` — исправления уязвимостей
