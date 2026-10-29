# Правила разработки AI Teacher for Python

> Этот документ — обязателен к прочтению каждым участником проекта (включая
> DSH и любых AI-ассистентов). Он дополняет `Design.md` и `TODO.md`, но не
> заменяет их: `Design.md` — источник истины по архитектуре, `TODO.md` — по
> порядку работ, `RULES.md` — по тому, **как** эти работы выполняются.

## Оглавление

1. [Принципы](#1-принципы)
2. [Ветвление и коммиты](#2-ветвление-и-коммиты)
3. [Код](#3-код)
4. [Тесты](#4-тесты)
5. [Документация](#5-документация)
6. [Итерации и отчёты](#6-итерации-и-отчёты)
7. [Безопасность](#7-безопасность)
8. [Работа с LLM](#8-работа-с-llm)
9. [Обработка блокеров](#9-обработка-блокеров)
10. [Чек-лист перед коммитом](#10-чек-лист-перед-коммитом)
11. [Окружение и воспроизводимость](#11-окружение-и-воспроизводимость)
12. [Отчёты по шагам итерации](#12-отчёты-по-шагам-итерации)

---

## 1. Принципы

- **Факты — от кода, объяснения — от LLM.** Любой код, предложенный учеником,
  должен быть выполнен в sandbox и проверен. LLM не имеет права "придумывать"
  результат выполнения.
- **Уровень — это политика, а не только промпт.** Ответ ассистента определяется
  комбинацией промпта, анализа кода и образовательной стратегии уровня.
- **Источник истины — один.** Архитектурные решения — только в `Design.md`.
  Дублирование факта в нескольких документах запрещено; вместо этого — ссылка.
- **Не перескакивать через зависимости.** В `TODO.md` у каждой задачи указано
  `Зависит от:`. Если зависимость не закрыта — задача не начинается.
- **Блокер — это нормально.** Лучше завести `KI-NNN` и остановиться, чем
  обойти проблему "временным решением", которое потом забывается.
- **Маленькие итерации.** Одна итерация — один спринт из `TODO.md`.
  В конце итерации — зелёный CI и отчёт в `RELEASES.md`.
- **Код — на Python 3.12, Frontend — на React 19.** Не меняем стек без согласования.

---

## 2. Ветвление и коммиты

### 2.1. Ветки

- `main` — всегда зелёная, всегда готова к деплою.
- `sprint/N-<slug>` — рабочая ветка спринта. Пример:
  `sprint/01-project-setup`, `sprint/06-code-execution`.
- `fix/KI-NNN-<slug>` — исправление известной проблемы. Пример:
  `fix/KI-012-executor-timeout-overflow`.
- `exp/<slug>` — эксперименты, не идущие в `main` напрямую.

Мерж в `main` — только через PR с зелёным CI и ревью.

### 2.2. Сообщения коммитов — Conventional Commits

```
<type>(<scope>): <subject>

[optional body]

[optional footer: Refs: S-N-NNN, KI-NNN]
```

**Типы:** `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`.

**Scope** — модуль или задача: `auth`, `chat`, `code`, `tasks`, `frontend`, `docs`, `ci`.
Допускается `S1-001` вместо scope, если задача крупная.

**Примеры:**

```
feat(chat): implement WebSocket streaming for LLM responses (S4-006)
fix(executor): handle memory limit exceeded error (KI-007)
docs(rules): add commit message conventions
test(auth): cover JWT token refresh scenarios (S3-005)
```

**Запрещено:**
- Коммитить с `--no-verify` (pre-commit хуки обязательны).
- Коммитить секреты (`.env`, ключи, токены).
- Смешивать в одном коммите несвязанные изменения.

### 2.3. PR

- Название PR = `<type>(<scope>): <краткое описание> (S-N-NNN..S-M-MMM)`.
- В описании — ссылки на задачи из `TODO.md` и отчёт спринта.
- CI должен быть зелёным. Красный CI — PR не мержится.
- Ревьюер проверяет чек-лист §10.

### 2.4. Стандарт отчётов по спринту (7 разделов)

> Каждый отчёт о спринте — строго 7 разделов:
> **(1) Файлы (+/-)** — созданные/изменённые пути;
> **(2) Покрытие** — новые/обновлённые тесты;
> **(3) Результаты** — Build 0/0 и Tests X/Y;
> **(4) Smoke** — ручной сценарий проверки;
> **(5) Что не так** — известные ограничения/риски;
> **(6) Новые KI** — зарегистрированные KI или "нет";
> **(7) Обоснование** — почему выбрана такая архитектура.
> Файл отчёта: `docs/reports/sprint-N/SPRINT-N.md`.

---

## 3. Код

### 3.1. Backend (Python 3.12)

- **Стиль:** `ruff` с конфигом из `pyproject.toml` (`line-length = 100`,
  `target-version = "py312"`). Нарушения — блокер для мержа.
- **Типы:** `mypy --strict` обязателен. Публичные функции и методы — с
  аннотациями. `Any` — только с `# type: ignore[...]` и комментарием.
- **Async:** весь I/O — `async`/`await`. Синхронные блокирующие вызовы
  — только через `asyncio.to_thread` / `run_in_executor`.
- **Pydantic v2:** все входы/выходы API — через `BaseModel`. Никаких
  "голых" `dict` в публичных сигнатурах.
- **SQLAlchemy 2.0:** `Mapped[...]`, `mapped_column`. Никаких старых
  `declarative_base()` и `Column(...)`.
- **Alembic:** одна миграция — одно логическое изменение. Автогенерация —
  только с ревью; ручные правки миграций допустимы.
- **Логи:** `structlog`, structured JSON. Никаких `print()`. Уровни:
  `debug` — для отладки, `info` — для бизнес-событий, `warning` — для
  восстановимых проблем, `error` — для сбоев.
- **Ошибки:** собственные исключения в `app/errors.py`. `HTTPException`
  только на уровне API.
- **Конфиг:** только через `Settings` (pydantic-settings). Чтение
  `os.environ` напрямую — запрещено.

### 3.2. Frontend (React 19 + TypeScript)

- **Стиль:** `tsc --noEmit` обязателен, `strict: true`. `any` — только с
  `// eslint-disable-next-line` и комментарием.
- **Компоненты:** функциональные, без классов. Хуки — по правилам React.
- **Состояние:** Zustand для глобального, `useState` для локального.
- **Запросы:** `fetch` обёрнут в `lib/api.ts` с типами. Ответы
  валидируются схемами.
- **Стили:** Tailwind CSS 4. Никаких inline-стилей, кроме экспериментов
  (которые не мержатся).
- **i18n:** все строки — через `react-i18next`. Хардкод строк в JSX —
  запрещён.
- **Производительность:** route-level code-split для страниц. Основной
  чанк — ≤ 200 kB (gzip).

### 3.3. Общее

- **Не менять стек** без явного согласования (Python 3.12, FastAPI, React 19,
  PostgreSQL 17 + pgvector, Redis, DeepSeek/LM Studio).
- **Не добавлять зависимости** без обоснования в PR.
- **Не коммитить сгенерированные файлы** (`dist/`, `__pycache__/`,
  `node_modules/`).
- **Не коммитить локальные данные** (`data/`, `.env`, `.venv/`).

---

## 4. Тесты

### 4.1. Обязательный минимум

- **Каждая новая функция/метод** — с unit-тестом. Если тривиальна — явно
  указать в PR.
- **Каждый эндпоинт API** — с интеграционным тестом (FastAPI TestClient).
- **Каждая миграция** — тест на `upgrade` + `downgrade` + повторный `upgrade`.
- **Каждый уровень ассистента** — тест на корректность промпта.
- **Каждый executor** — тест на безопасность (dangerous code blocked).

### 4.2. Пирамида

- **Unit** — 70%: чистая логика, без БД и сети.
- **Integration** — 25%: API + БД (testcontainers), LLM (mock).
- **E2E** — 5%: Playwright на фронтенде + полный сценарий.

### 4.3. Структура

```
tests/
├── unit/
│   ├── test_security.py
│   ├── test_executor.py
│   ├── test_levels.py
│   └── ...
├── integration/
│   ├── test_auth_api.py
│   ├── test_chat_api.py
│   ├── test_tasks_api.py
│   └── ...
├── e2e/
│   └── test_full_flow.py
└── fixtures/
    ├── sample_tasks.json
    └── ...
```

### 4.4. Правила

- **Тесты не должны зависеть от порядка выполнения.**
- **Тесты не должны ходить в интернет.** LLM — через моки.
- **Тесты не должны разделять состояние.**
- **Flaky-тесты — блокер.** Завести `KI-NNN`, починить или `@pytest.mark.skip`.
- **Покрытие:** целевое ≥ 80% для `app/`, ≥ 60% для `frontend/src/`.

---

## 5. Документация

### 5.1. Что и где

- **`Design.md`** — единственный источник истины по архитектуре.
- **`TODO.md`** — порядок работ и зависимости.
- **`docs/RULES.md`** — этот документ.
- **`docs/GETTING_STARTED.md`** — как развернуть за 20 минут.
- **`docs/USER_GUIDE.md`** — как пользоваться.
- **`docs/ARCHITECTURE.md`** — как это устроено.
- **`docs/RELEASES.md`** — журнал спринтов.
- **`docs/CHANGELOG.md`** — по [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).
- **`docs/KNOWN_ISSUES.md`** — реестр проблем (`KI-NNN`).

### 5.2. Правила

- **Один факт — один источник.** Дублирование запрещено.
- **Каждый PR** обновляет затронутые документы.
- **Язык:** документация — на русском. README — на русском + английском.
- **Формат:** markdown, GFM-совместимый.

---

## 6. Итерации и отчёты

### 6.1. Планирование

- Итерация = один спринт из `TODO.md`.
- В начале спринта — план в `docs/RELEASES.md`: задачи, порядок, риски.
- Если задача оказалась больше — разбей на подзадачи (`S-N-NNNa`, `S-N-NNNb`).

### 6.2. Выполнение

- Работай по шагам, после каждого — проверяй результат (`ruff`, `mypy`,
  `pytest`, `pnpm typecheck`).
- Каждый шаг — отдельный коммит.
- Блокер — сразу `KI-NNN` и стоп.

### 6.3. Завершение спринта

Спринт завершён, когда:

1. Все задачи закрыты (`[x]` в `TODO.md`), или явно перенесены в `KNOWN_ISSUES.md`.
2. `ruff check .`, `mypy app`, `pytest -q` — зелёные.
3. `pnpm --dir frontend typecheck && pnpm --dir frontend build` — зелёные.
4. CI — зелёный.
5. Отчёт в `docs/RELEASES.md` заполнен.
6. `docs/CHANGELOG.md` обновлён.
7. PR в `main` создан и смержен.

---

## 7. Безопасность

### 7.1. Секреты

- **Никогда** не коммитить `.env`, ключи API, пароли, токены.
- Все секреты — в ENV (dev) или Vault (prod).
- `.env.example` содержит только placeholder'ы (`change_me_*`).
- Pre-commit блокирует коммиты с паттернами реальных ключей.

### 7.2. Аутентификация и авторизация

- JWT + refresh-токены. Access — 30 минут, refresh — 7 дней.
- Роли: `student`, `teacher`, `admin`. Проверки — на уровне эндпоинта.
- Rate limiting: 5/мин на login, 300/мин общий.

### 7.3. Code Execution Security

- **RestrictedPython** обязателен.
- Timeout: 5 секунд максимум.
- Memory limit: 128 MB.
- No file system, no network, no dangerous imports.
- Логировать попытки нарушения безопасности.

### 7.4. Валидация входных данных

- Все входы — через Pydantic-схемы с `strict=True`.
- Python код — валидируется перед выполнением.
- Загружаемые файлы — лимит размера (10 MB).

---

## 8. Работа с LLM

### 8.1. Общие правила

- **Промпты версионируются.** `app/services/llm/prompts/<level>.txt` — файлы.
- Изменение промпта — отдельный PR с тестом.
- **Стоимость контролируется.** `max_tokens` и `cost_cap` на запрос.
- **Fallback.** Если DeepSeek недоступен — fallback на LM Studio.

### 8.2. Три уровня

- **Basic:** наводящие вопросы, метафоры, аналогии. НЕ давать готовый код.
- **Intermediate:** объяснение с примерами, частичные решения.
- **Advanced:** полные решения с детальными объяснениями.

### 8.3. Контекст

- Сбор контекста из истории чата (последние N сообщений).
- Injection системного промпта в зависимости от уровня.
- Truncation для длинных диалогов.

---

## 9. Обработка блокеров

### 9.1. Что считается блокером

- Шаг не выполняется из-за внешней причины.
- Тест падает нестабильно (flaky).
- Обнаружено противоречие в `Design.md` или `TODO.md`.
- Обнаружена уязвимость или утечка секрета.

### 9.2. Что делать

1. **Завести `KI-NNN`** в `docs/KNOWN_ISSUES.md`.
2. **Пометить задачу** в `TODO.md` как `[~]` со ссылкой на `KI-NNN`.
3. **Остановиться.** Не обходить "временным решением".
4. **Сообщить.**

### 9.3. Severity

- **Critical** — блокирует весь проект.
- **High** — блокирует текущий спринт.
- **Med** — блокирует одну задачу.
- **Low** — не блокирует, но стоит починить.

---

## 10. Чек-лист перед коммитом

- [ ] `ruff check backend/` — 0 ошибок.
- [ ] `mypy app --config-file ../pyproject.toml` (из `backend/`) — 0 ошибок.
- [ ] `alembic upgrade head` + `alembic check` — схема БД совпадает с моделями.
- [ ] `pytest -q` — все passed.
- [ ] `pnpm --dir frontend typecheck` — 0 ошибок (если трогал frontend).
- [ ] `pnpm --dir frontend build` — собирается (если трогал frontend).
- [ ] Нет закомментированного кода "на будущее".
- [ ] Нет `print()` / `console.log()`.
- [ ] Нет секретов в коде и в диффе.
- [ ] Нет сгенерированных файлов в диффе.
- [ ] Обновлены затронутые документы.
- [ ] Сообщение коммита соответствует Conventional Commits.
- [ ] Ссылка на задачу (`S-N-NNN`) или `KI-NNN`.

---

## 11. Окружение и воспроизводимость

### 11.1. Адреса: `127.0.0.1`, а не `localhost`

На Windows `localhost` резолвится сначала в `::1`, а Docker Compose
публикует порты только на IPv4-loopback (`127.0.0.1`).

- `POSTGRES_HOST=127.0.0.1`, `REDIS_URL=redis://127.0.0.1:<port>/0`.
- В `docker-compose.yml` порты публикуются как
  `"127.0.0.1:${PORT:-default}:<container>"`.

### 11.2. Порты

- Канон: Postgres `5432`, Redis `6379`, API `8000`, Frontend `3000`.
- `.env` — локальный, в git не попадает; `.env.example` хранит канон.
- **Факт на текущей машине (KI-001):** `5432` занят контейнером `ticket-postgres`,
  `6379` — `workflow-builder-redis`. Поэтому проект использует
  Postgres `5434` и Redis `6381`.
- Чужой контейнер **не останавливаем**. Внешние порты берём из ENV:
  `POSTGRES_PORT`, `REDIS_PORT` — они подставляются в `docker-compose.yml`
  и читаются `Settings` (дефолты в `app/config.py` тоже `5434`/`6381`).
- Внутри compose-сети сервисы общаются по внутренним портам (`postgres:5432`,
  `redis:6379`) — их менять не нужно.
- Урок KI-001: если контейнер не смог опубликовать порт, подключение уходит
  на **чужой** сервис и падает с непонятной ошибкой аутентификации. Всегда
  проверяйте `docker compose ps` — в колонке PORTS должен быть `0.0.0.0:PORT->`
  или `127.0.0.1:PORT->`, а не голый `<port>/tcp`.

### 11.3. Python

- Python 3.12 обязателен; на текущей машине установлен 3.11.8 — тесты и сервис
  работают, но CI гоняет 3.12.
- Poetry или pip + venv.
- Версии библиотек фиксируются в `requirements.txt`.

### 11.4. Конфигурация: `.env` в корне проекта

- `app/config.py` читает `.env` по абсолютному пути
  (`Path(__file__).resolve().parents[2]`), а не относительно CWD. Иначе при
  запуске `alembic`/`pytest` из `backend/` настройки тихо подменяются
  дефолтами — так порт 5434 превращался в 5432 и запросы уходили в чужую БД.
- `allowed_origins` в `.env` задаётся CSV (`a,b`) — парсер в
  `Settings.parse_allowed_origins` поддерживает и JSON-массив.
- Конфиг `mypy` живёт в корневом `pyproject.toml`; mypy из `backend/`
  запускается с `--config-file ../pyproject.toml`, иначе строгие правила
  не применяются и ошибки типизации не ловятся.

### 11.5. База данных и миграции

Ловушки, на которые уже наступали:

1. **Образ Postgres.** `postgres:17-alpine` не содержит `pgvector` →
   `extension "vector" is not available`. Нужен `pgvector/pgvector:pg17` (KI-003).
2. **`server_default` для JSONB.** `server_default=sa.text("{}")` невалиден:
   нужен `sa.text("'{}'::jsonb")` (и `'[]'::jsonb` для массивов).
3. **Enum хранит имена, а не значения.** `Enum(Role)` пишет `STUDENT`, тогда как
   тип создан со значениями `student`. Обязательно
   `values_callable=lambda enum_cls: [e.value for e in enum_cls]` (KI-004).
4. **`metadata` — занятое имя** в `DeclarativeBase`. Колонку `metadata`
   объявляем как `session_metadata` с `mapped_column("metadata", ...)`.
5. **`create_all` не заменяет миграции.** Тесты создают схему из моделей и потому
   не видят расхождений с Alembic. Перед коммитом — `alembic check` (KI-002).
6. После любой правки миграции: `alembic upgrade head`, `alembic check`,
   `alembic downgrade base && alembic upgrade head`.
7. **Lazy-relationship в async — `MissingGreenlet`.** Обращение вида
   `if task.progress:` внутри async-сервиса падает. Используйте
   `selectinload` или отдельный запрос (`exists_for_task`), как в
   `TaskService.delete_task`.
8. **Данные для разработки — отдельный скрипт.** Учебные задачи добавляет
   `backend/scripts/seed_tasks.py` (идемпотентно, по заголовку), а не миграция
   (KI-010).

### 11.6. Пароли и bcrypt

- `passlib 1.7.4` несовместим с `bcrypt 5.x` (`ValueError` на 72+ байтах,
  `no attribute '__about__'`). Используем `bcrypt` напрямую (KI-005).
- bcrypt не принимает пароль длиннее 72 байт: ограничение продублировано
  в `UserCreate.password` (`max_length=72`), чтобы клиент получал 422, а не 500.

### 11.7. Тесты на Windows

- Тесты работают на реальном PostgreSQL (SQLite не поддерживает JSONB/VECTOR).
- Создание тестовой БД — синхронная session-scoped фикстура (`psycopg2`):
  async-фикстуры другого scope привязываются к чужому event loop и ломают asyncpg.
- Клиент в тестах — `httpx.AsyncClient` + `ASGITransport`; `TestClient` нельзя
  совмещать с async-фикстурой БД.
- Каждый тест выполняется в транзакции с откатом
  (`join_transaction_mode="create_savepoint"`), поэтому коммиты внутри
  репозиториев не «протекают» между тестами.

### 11.8. Песочница кода (RestrictedPython)

Ловушки, проверенные на практике:

1. **Поток нельзя убить.** `asyncio.wait_for` + `to_thread` не останавливает
   `while True`: поток продолжает работать, процесс живёт. Выполняем код в
   отдельном интерпретаторе и убиваем его по таймауту.
2. **`multiprocessing` + uvicorn на Windows.** `spawn` перезапускает
   `__main__` → «Safe importing of main module». Используем `subprocess` с
   `sys.executable -c`.
3. **`_print_` — это класс `PrintCollector`.** RP 7 сам инстанцирует его
   (`_print = _print_(_getattr_)`). Собранный вывод лежит в
   `globals['_print']` и доступен вызовом `globals['_print']()`.
4. **`+=` требует `_inplacevar_`.** Без guard'а падает
   `NameError: name '_inplacevar_' is not defined`.
5. **`safe_builtins` не содержит `print`** и большинства встроенных функций —
   дополняем явно, но никогда не добавляем `open`, `eval`, `exec`.
6. **Лимит памяти** на Windows не enforced (KI-009): таймаут — единственная
   гарантия остановки.

### 11.9. Промпты уровней

- Промпты — файлы `app/services/llm/prompts/<level>.txt`, а не строки в коде.
- Тесты проверяют наличие обязательных маркеров политики уровня
  (базовый запрещает готовый код, продвинутый требует полное решение).
- Если файла промпта нет — `resolve_level` откатывает на `basic`, чат не падает.

### 11.10. Frontend (pnpm 12, Vite 6, TS)

Ловушки, проверенные на практике:

1. **pnpm 12 блокирует build-скрипты.** `pnpm install` падает с
   `ERR_PNPM_IGNORED_BUILDS`. Настройки живут в `frontend/pnpm-workspace.yaml`
   (`onlyBuiltDependencies: [esbuild]`); разово — `pnpm install --allow-build=esbuild`.
2. **`defineConfig` для тестов.** Секция `test` типизируется только из
   `vitest/config`, иначе `tsc -b` падает на «'test' does not exist».
3. **Project references.** `pnpm build` = `tsc -b && vite build`;
   `vite.config.ts` проверяется отдельным `tsconfig.node.json` (нужен `@types/node`).
4. **Регистр директорий.** Windows не различает `Layout` и `layout`, Linux — да.
   Все каталоги `src/components/*` пишем в нижнем регистре (`components/layout`).
5. **Прокси в dev.** Vite проксирует `/api` → `http://127.0.0.1:8000`
   (`127.0.0.1`, не `localhost` — см. §11.1); CORS в dev не нужен.
6. **`import.meta.env`** требует `src/vite-env.d.ts` с объявлением `ImportMetaEnv`.
7. **Алиасы путей** задаются дважды: `tsconfig.app.json#paths` и `vite.config.ts#resolve.alias`.
8. **jsdom не реализует `scrollIntoView`** — в компонентах вызывайте его опционально
   (`el?.scrollIntoView?.(...)`), иначе тесты падают на монтировании.
9. **Правило react-refresh.** Файл с компонентом не должен экспортировать ещё и
   утилиты: `splitCodeFences` вынесена в `lib/markdown.ts`, иначе ESLint даёт warning.
10. **Monaco в тестах.** `@monaco-editor/react` мокается в `src/test/setup.ts`
    на `textarea`; в рантайме Monaco грузится с CDN (KI-013).

---

## 12. Отчёты по шагам спринта

Каждый шаг спринта документируется отдельным файлом:

```
docs/reports/sprint-N/STEP-MM_<ТЕМА>.md
```

Обязательные разделы:

1. **Шапка:** дата, спринт, задача (`S-N-NNN`), статус.
2. **Что сделано** — нумерованный список.
3. **Проверки** — таблица "проверка → команда → результат".
4. **Файлы** — что создано/изменено.
5. **Проблемы и отклонения** — со ссылками `KI-NNN`.
6. **Обоснование решений** — варианты, что выбрали.
7. **Что дальше** — следующий шаг.

---

## Приложение A. Полезные команды

```bash
# Backend
ruff check . --fix
mypy app
pytest -q
pytest -q tests/integration
alembic revision --autogenerate -m "message"
alembic upgrade head

# Frontend
pnpm --dir frontend install
pnpm --dir frontend typecheck
pnpm --dir frontend build
pnpm --dir frontend test

# Docker
docker compose up -d postgres redis
docker compose ps
docker compose logs -f postgres

# Healthcheck
curl -s http://localhost:8000/api/v1/health | python -m json.tool
```

---

## Приложение B. Ссылки

- [Design.md](../Design.md) — источник истины по архитектуре.
- [TODO.md](../TODO.md) — порядок работ.
- [CHANGELOG.md](CHANGELOG.md) — история версий.
- [KNOWN_ISSUES.md](KNOWN_ISSUES.md) — реестр проблем.
- [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).
- [Conventional Commits](https://www.conventionalcommits.org/ru/).
