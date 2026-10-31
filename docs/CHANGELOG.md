# CHANGELOG.md — История версий

Все заметные изменения в проекте документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
и проект следует [Semantic Versioning](https://semver.org/lang/ru/).

---

## [Unreleased]

Этап v0.3.0 «Ops & Scale» (спринты 21–30). Спринт 21 — CI & Quality Gates.

### Добавлено

**CI (S21)**

- CI снова запускает проверки: workflow `CI (self-hosted fallback)` на
  Windows-runner'е (`C:\actions-runner`) — `Lint (backend)`, `Test (backend)`,
  `Frontend`, `Security`, `E2E (Playwright)`, `Docker build`; прогон 6/6
  зелёный, минуты GitHub не расходуются (KI-014)
- Переиспользуемый набор гейтов (`workflow_call`) — его же вызывает релиз,
  команды не дублируются
- Path-фильтры: docs-only PR не гоняет e2e/docker (GitHub `paths-ignore`,
  GitFlic `rules: changes:`)
- Офлайн-путь зависимостей для CI: wheelhouse в named volume
  `ai-teacher-wheelhouse` (`scripts/ci/build-wheelhouse.ps1`,
  `scripts/ci/install-python-deps.sh`) + постоянные кэши pip/pnpm — job'ы не
  зависят от нестабильного PyPI (KI-017)
- Релиз одной командой: `.github/workflows/release.yml` (гейты → тег →
  GitHub Release), dry-run по умолчанию, репетиция по тегу `v*-dryrun`,
  заметки — из `docs/RELEASES.md`
- `scripts/ci/protect-branch.ps1` — готовая защита ветки (6 required checks,
  запрет force-push) с честной диагностикой 403 на GitHub Free/private
- GitFlic: полный `gitflic-ci.yaml` (5 job'ов + 3 security + e2e/docker на
  PowerShell-агенте + тег-джоб `release`), пилотный `ci/gitflic-pilot.yaml`,
  рунбук `docs/GITFLIC_RUNNER.md`, настройка проекта `scripts/gitflic/setup.ps1`
- `docs/CI.md` — платформа, гейты, релиз, эксплуатация runner'а; RULES §11.20

### Изменено

- `pytest`/`ruff`/`mypy` в CI ставятся из `backend/requirements.txt`
  (закреплённые версии): unpinned ruff давал 54 ложных ошибки на неизменённом
  коде, а mypy без runtime-зависимостей — 295 `import-not-found`
- GitHub-hosted `ci.yml` переведён в ручной режим до восстановления биллинга
  (KI-014) — красный workflow больше не висит на каждом PR
- `E2E_PYTHON` для runner'а указывает на актуальный venv проекта

---

## [0.2.0] - 2026-10-30

Релиз «Classroom»: классы и назначения, достижения и дашборд, UX/тёмная
тема, производительность (S19) и безопасность/эксплуатация (S20).

### Добавлено

**Производительность и масштаб (S19)**

- Redis-кэш справочников (`/chat/levels`, `/tasks/categories`) и каталога
  задач (`/tasks`): TTL 60 с, ключ включает пользователя и все фильтры,
  инвалидация при CRUD/импорте/seed/откате версии; fail-open и 10-секундное
  «остывание» после сбоя Redis; метрики `cache` в `/admin/analytics`
- Пагинация `GET /classrooms`, `GET /me/notifications`, `GET /teacher/tasks`
  (`total` — по всей таблице, а не по странице); N+1 в классах устранены
  одним агрегирующим запросом
- Индексы миграции 0009 под каталог/учеников/уведомления/дедлайны/историю
  сообщений; HNSW-индекс `chat_messages.embedding` (миграция 0010)
- Поиск по истории чата `GET /chat/search` (RAG-lite): семантический режим
  (pgvector, HNSW) за флагом `RAG_ENABLED`, ILIKE-фолбэк, только свои
  сообщения; best-effort эмбеддинги — сбой провайдера не ломает чат
- Нагрузочный тест S19-006 (httpx-генератор вместо k6/locust — PyPI с хоста
  заблокирован): `health` 50 RPS — p95 **6.3 мс**, каталог 20 RPS — p95
  **25.4 мс** (0 ошибок, PASS); `submit` — knee ≈2 RPS, целевые 5 RPS не
  достигнуты (факт 2.5 RPS, p95 2219.7 мс при бюджете 2000 мс) — ограничение
  песочницы, **KI-022**, рекомендации в `reports/sprint-19/LOAD_TEST.md`
- Локальный Monaco без CDN: ассеты `public/monaco/vs`, lazy-чанк,
  `pnpm test:offline` (KI-013)
- Code splitting всех маршрутов: vendor-чанки; entry — 76.3 kB gzip на S19-002,
  **78.71 kB gzip** после финальной сборки v0.2.0 (лимит 80)

**Безопасность и эксплуатация (S20)**

- Аудит зависимостей: `pnpm audit` — **0** уязвимостей; backend — **0
  critical**, остаточные записи (`starlette`, dev `pytest`) приняты и
  задокументированы (KI-015, KI-016)
- `python-jose` удалён → **PyJWT 2.15.1**; `python-multipart` 0.0.17 → **0.0.31**
- RestrictedPython 7.4 → **8.5**: закрыты 3 high-обхода песочницы; `.format()`
  и `string.Formatter` теперь запрещены с понятной подсказкой
  (`error_type=RestrictedFeatureError`)
- `.gitleaks.toml` + CI job `Security` (`pip-audit`, `gitleaks`,
  `pnpm audit`); `.github/dependabot.yml` (pip/npm/github-actions, weekly)
- nginx: CSP + `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy`, `HSTS`; `server_tokens off`;
  `ALLOWED_ORIGINS` в prod-compose — из ENV
- `scripts/backup.sh` и `scripts/restore.sh`: бэкап через
  `docker exec pg_dump` + gzip + sha256, retention, guard от перезаписи
  рабочей БД; smoke — 14/14 таблиц восстановлено
- `backend/scripts/audit_python_deps.py` — офлайн-аудит по GitHub Advisory
  API для машины без PyPI (лимит 60 запросов/час, кэш, `--resume`)
- `/tasks/{id}/hints/{index}` требует аутентификации (S20-003, находка F1);
  автотест матрицы доступа `backend/tests/test_access_matrix.py` — **35 тестов,
  IDOR не найден** (отчёт `docs/reports/sprint-20/ACCESS_MATRIX.md`)
- Финальная документация v0.2.0: SPEC, CHANGELOG, RELEASES, KNOWN_ISSUES,
  RULES §11.18–11.19, MANUAL_TESTING_GUIDE, отчёты sprint-19/sprint-20

**Функциональность и UX (S11–S18)**

- Тёмная тема: переключатель в шапке/профиле, `localStorage`, Monaco `vs-dark`
- Дизайн-система: токены, `Modal`, `Toast`, `Tabs`, `Table`, `Badge`,
  `Skeleton`; dev-страница `/dev/ui` вне прод-бандла
- Доступность: skip-link, aria-разметка, `vitest-axe` на входе/регистрации
- Мобильное меню и drawer сессий чата
- Достижения (`achievements`, `user_achievements`, миграция 008): 6 правил,
  выдача при submit, `GET /me/achievements`
- `GET /me/stats`: решено, серия дней (UTC+3), средние попытки, активность в чате
- Дашборд `/dashboard`: прогресс-бар, streak, последние задачи, достижения
- In-app уведомления (`notifications`): назначение, дедлайн ≤72 ч, достижение;
  `GET /me/notifications` и отметка прочитанным
- Классы: `classrooms`, `classroom_members`, `assignments` (миграция 007);
  создание, вступление по коду, исключение участника
- Назначения задач классу с дедлайнами, `/me/assignments`, матрица прогресса
  класса; UI `/classrooms`, `/classrooms/:id`, `/assignments`
- Кабинет учителя: `/teacher/tasks` (CRUD, тест-кейсы, импорт с предпросмотром)
  и `/teacher/students` (агрегаты и прогресс по задачам)
- API учителя: `/teacher/tasks`, `/teacher/students`,
  `/teacher/students/{id}/progress`; импорт файла `/tasks/import/file`
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
- `/admin/analytics` расширен секцией `cache` (hits/misses/hit_rate/sets/
  invalidations/errors)
- Списочные эндпоинты получили аддитивную пагинацию (`skip`/`limit`),
  дефолты сохраняют прежнее поведение
- Песочница: RestrictedPython 8.5; для ограниченных возможностей возвращается
  `error_type=RestrictedFeatureError` вместо сырого `NotImplementedError`
- nginx: заголовки безопасности на уровне `server`, кэш `/assets/` через
  `expires` (без `add_header`, чтобы не отключать наследование)
- CI: job `Security`; prod-compose берёт `ALLOWED_ORIGINS` из ENV

### Исправлено
- После перезагрузки страницы защищённые маршруты висели на Spinner:
  `loadMe()` теперь вызывается при старте приложения
- Лимит памяти песочницы на Windows больше не «декоративный»: Job Object
  реально ограничивает committed memory (KI-009)
- Промпт среднего уровня: примеры — на других данных, при просьбе «напиши
  программу» — только каркас и шаги; версия промпта intermediate = 2
  (по итогам живого прогона, KI-008)
- `GET /tasks/{id}/hints/{index}` больше не анонимный: требуется токен
  (S20-003, найдено аудитом доступа)
- Prod-Docker: backend-контейнер применяет миграции при старте
  (`docker-entrypoint.sh` → `alembic upgrade head`, отключается
  `SKIP_MIGRATIONS=true`); на чистой БД API больше не падает с
  `UndefinedTableError` (S20-006)
- `.dockerignore` для backend/frontend: venv, кэши, `node_modules`, `dist` и
  ассеты Monaco больше не попадают в контекст сборки (S20-006)
- Каталог задач больше не «протекает» между учениками: ключ кэша включает
  `user_id` и все фильтры (S19-003)

### Безопасность
- Удалён `python-jose 3.3.0` (2 critical + 1 moderate; транзитивные `ecdsa`/
  `rsa` тоже ушли), JWT переведён на **PyJWT 2.15.1** (закрыты все известные
  GHSA: 2.10.0 → 2.15.1)
- `python-multipart` 0.0.17 → **0.0.31** (GHSA-wp53-j4wj-2cfg,
  GHSA-pp6c-gr5w-3c5g, GHSA-5rvq-cxj2-64vf, GHSA-v9pg-7xvm-68hf)
- RestrictedPython 7.4 → **8.5**: GHSA-gmj9-h825-chq2 (`try/except*` type
  confusion), GHSA-ffg3-p8fm-mjx2 (shadowing guard-хуков),
  GHSA-hp3v-5vw7-fx9w (`string.Formatter` field resolution) — 3 high обхода
  песочницы закрыты; побочный эффект — `.format()`/`format_map()`/
  `string.Formatter` запрещены (KI-018), f-строки и `%` работают
- Frontend: `vitest`/`@vitest/coverage-v8` 3.2.7 → **4.1.12**
  (tinypool GHSA-5gmw-xhrv-c9v3, GHSA-85c8-ppgw-ccpr — 2 critical +
  3 moderate dev-зависимостей закрыты; `pnpm audit` — 0)
- nginx CSP без `unsafe-eval` (Monaco и worker'ы работают), HSTS,
  `frame-ancestors 'none'`; секреты в prod-compose обязательны (`:?`),
  `DEBUG=false`, БД/Redis не публикуются
- `gitleaks` 8.30.1: 0 утечек на 42 коммитах; правила под проект
  (`deepseek-api-key`, `postgres-password-in-url`, `jwt-secret-assignment`)
- Остаточные риски приняты и отслеживаются: KI-015 (starlette 0.41.3 —
  транзитивно от `fastapi 0.115.5`, неиспользуемые векторы), KI-016
  (dev-only `pytest 8.3.3`); `pip-audit` — 0 critical, CI-команда с 8
  временными `--ignore-vuln` (7 starlette + 1 pytest) даёт
  «No known vulnerabilities found, 16 ignored», exit 0

### Удалено
- `python-jose` (и транзитивные `ecdsa`, `rsa`) — заменён на PyJWT
- `@monaco-editor/react` — заменён на локальный `monaco-editor` (S19-001)

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
