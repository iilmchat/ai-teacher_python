# KNOWN_ISSUES.md — Реестр известных проблем

> Этот документ содержит список всех известных проблем, ограничений и блокеров.
> Каждая проблема имеет ID `KI-NNN`, статус, severity и план закрытия.

**Последнее обновление:** 2026-10-31 (спринт 22 / v0.3.0 — Dependency Modernization)  
**Всего проблем:** 23 (активных: 4, закрытых: 19)

---

## Шаблон записи

```
KI-NNN · <статус> · <severity> · <модули> · <план закрытия>

Описание: что происходит
Окружение: версия, OS, etc
Воспроизведение: шаги
Workaround: временное решение (если есть)
Создано: дата
Обновлено: дата
```

**Статусы:** `Open`, `In Progress`, `Blocked`, `Resolved`, `Closed`  
**Accepted** — риск/ограничение принято осознанно и отслеживается: не блокирует
релиз, план — в рамках планового апгрейда или пересмотра решения.

**Severity:** `Critical`, `High`, `Med`, `Low`

---

## Активные проблемы

### KI-023 · Open · High · CI · merge-gate не обеспечен: GitHub Free не даёт required checks, GitFlic-пилот ждёт доступа

**Описание:** зелёный CI восстановлен (KI-014), но *заблокировать* мерж красного
PR нечем: GitHub Free для приватного репозитория отвечает `403 Upgrade to GitHub
Pro or make this repository public` на `PUT /repos/.../branches/main/protection`
(проверено 2026-10-30, дважды). GitFlic даёт защиту ветвей и опцию «Проверять
статус последнего конвейера при слиянии» на бесплатном тарифе, но пилот
(S21-002) требует access token GitFlic и зарегистрированного агента — это доступ
владельца, у агента разработки его нет.

**Что уже готово:** `scripts/ci/protect-branch.ps1` (payload с 6 required
checks, запрет force-push, `-DryRun`/`-Verify`); `gitflic-ci.yaml` с MR-правилами;
ADR и инструкции — `docs/CI.md` §10; проверка того, что красный пайплайн
блокирует merge, описана пошагово.

**Workaround:** RULES §10 — мерж только при зелёном `CI (self-hosted fallback)`
(проверка глазами), зелёный прогон 6/6 известен (run 41070317162).

**План закрытия:** (1) владелец выдаёт GitFlic-токен/регистрирует агент →
прогнать пилот → включить гейт и проверить красным MR; либо (2) GitHub Pro /
публичный репозиторий → `pwsh scripts/ci/protect-branch.ps1`.

**Создано:** 2026-10-30 (S21-004) · **Обновлено:** 2026-10-30

---

### KI-017 · Open · Low · окружение/инструменты · PyPI недоступен с хоста

**Описание:** на машине разработки `pypi.org`/`files.pythonhosted.org`
заблокированы (connection reset/timeout): `pip install`/`pip-audit` с хоста
не работают, часть апгрейдов пришлось ставить вручную через Docker-wheelhouse.
Docker-контейнеры PyPI видят, npm registry и `api.github.com` доступны.

**Workaround:** аудит backend выполняется в контейнере (`python:3.12-slim`) —
это же путь CI; для локальной разработки — `backend/scripts/audit_python_deps.py`
по GitHub Advisory API (лимит 60 запросов/час, кэш, `--resume`, `--offline`,
exit 2 при неполном прогоне). Закрепление версий — `requirements.txt` +
Dependabot; авторитетный результат — CI `Security`.

**План закрытия:** восстановление доступа к PyPI на рабочей машине
(прокси/сеть) либо переход на локальное зеркало; до этого — процесс выше.

**Обновлено 2026-10-30 (спринт 21):** нестабильность стала заметнее — job
`lint` на self-hosted runner'е залипал в `pip install` на 20+ минут
(TLS-хендшейк к `pypi.org` таймаутил, при этом из свежего контейнера PyPI
отвечал). Для CI добавлен **офлайн-путь**: зависимости ставятся из wheelhouse
(named volume `ai-teacher-wheelhouse`, `scripts/ci/build-wheelhouse.ps1`), PyPI —
только fallback; плюс постоянные кэши pip/pnpm (`docs/CI.md` §12.5, RULES
§11.20). Сам доступ с хоста не восстановлен.

**Создано:** 2026-10-30 (S20-001) · **Обновлено:** 2026-10-30 (спринт 21)

---

### KI-018 · Accepted · Low · core/executor · `.format()` запрещён после RestrictedPython 8.5

**Описание:** RestrictedPython 8.5 закрывает обходы песочницы
(GHSA-hp3v-5vw7-fx9w и GHSA-ffg3-p8fm-mjx2) ценой полного запрета
`str.format`, `str.format_map` и `string.Formatter` — иначе field-resolution
снова даёт доступ к атрибутам. Для ученика это user-visible ограничение:
`"{x}".format(x=1)` теперь возвращает ошибку.

**Решение/политика:** f-строки (`f"{x}"`) и оператор `%` работают и
рекомендованы в подсказке; dunder-доступ внутри f-строк по-прежнему
заблокирован (`SecurityError`). Вместо сырого `NotImplementedError`
возвращается `error_type=RestrictedFeatureError` с русской подсказкой.
Задокументировано в USER_GUIDE, SPEC §5, RULES §11.8/§11.19; покрыто
тестами (`test_executor.py`, `test_sandbox_limits.py`).

**План пересмотра:** если RestrictedPython добавит безопасный форматтер —
пересмотреть; до этого ограничение принято (безопасность важнее удобства).

**Создано:** 2026-10-30 (S20-001b) · **Обновлено:** 2026-10-30

---

### KI-022 · Accepted · Med · performance/песочница · предел throughput submit (~2 RPS)

**Описание:** нагрузочный тест S19-006 (S19-006,
[LOAD_TEST.md](reports/sprint-19/LOAD_TEST.md)): `health` держит 50 RPS
(p95 6.3 мс), каталог — 20 RPS (p95 25.4 мс), а `submit` целевые 5 RPS не
достигает: факт 2.5 RPS, p50 1964 мс / p95 2219.7 мс при бюджете 2000 мс;
деградация на 3 RPS (p95 2387 мс). Точка насыщения ≈2 RPS, максимум
≈2.2–2.5 submit/s.

**Причина:** песочница, а не БД/HTTP. Один `submit` — 3 тест-кейса, каждый в
отдельном дочернем интерпретаторе Python (~0.5–0.6 с на кейс); при
`EXECUTOR_MAX_CONCURRENCY=4` это ≈7 exec/s ≈ 2.3 submit/s (сходится с
измерением). При `DEBUG=true` SQLAlchemy `echo` пишет каждый запрос и цифры
хуже — артефакт логирования, нагрузку запускать только с `DEBUG=false`.

**Почему принято в v0.2.0:** профиль зафиксирован и воспроизводим; 5 RPS
submit не входит в DoD релиза; деградация ограничена сценарием `submit`,
health/каталог имеют запас 47×/12×. Рекомендации — в отчёте LOAD_TEST §5.

**План:** v0.3.0 — прогонять все кейсы в одном дочернем процессе или пул
«тёплых» интерпретаторов; поднять `EXECUTOR_MAX_CONCURRENCY` (процессы
CPU-bound — рост до загрузки ядер); если 5 RPS submit — продуктовое
требование, защищать latency очередью с явным 429/503 и SLO, а не накоплением
очереди. Для CI — smoke ниже knee (submit 1–2 RPS, health 50, tasks 20).

**Создано:** 2026-10-30 (S19-006) · **Обновлено:** 2026-10-30

---

## Закрытые проблемы

### KI-014 · Resolved · High · CI · GitHub Actions не запускает job'ы (биллинг)

**Описание:** все GitHub-hosted job'ы завершались за 0–4 с без выполнения шагов;
аннотация API: «The job was not started because recent account payments have
failed or your spending limit needs to be increased». Код и workflow были ни
при чём (ruff/mypy/pytest/pnpm/e2e зелёные локально).

**Решение (S21, спринт 21):** CI восстановлен **без hosted-минут** —
self-hosted runner `ai-teacher-win` (labels `self-hosted, windows, ai-teacher`,
`C:\actions-runner`) и workflow `CI (self-hosted fallback)`. На нём — все 6
job'ов (Lint, Test, Frontend, Security, E2E, Docker), прогон **6/6 зелёный**
(run 41070317162, 12 мин 10 с). Сам биллинг hosted-минут остаётся вопросом
владельца: `ci.yml` переведён в ручной режим, чтобы не висел красным; после
оплаты/лимита достаточно вернуть `on: push/pull_request`. Merge-gate —
отдельная проблема **KI-023** (на Free/private required checks недоступны).

**Создано:** 2026-10-29 · **Закрыто:** 2026-10-30 (спринт 21, S21-003)

---

### KI-015 · Resolved · High · deps: fastapi/starlette · starlette 0.41.3 → 1.10.0

**Описание:** `starlette 0.41.3` (транзитивно от `fastapi 0.115.5`) содержал
7 advisory: high — PYSEC-2026-161, PYSEC-2026-248; medium/low — PYSEC-2026-1941,
1942, 2280, 2281, 249. Апгрейд требовал мажорного `starlette` (≥1.3.1) и
координированного апгрейда `fastapi`.

**Решение (S22-002, спринт 22):** `fastapi 0.115.5 → 0.162.0`,
`starlette 0.41.3 → 1.10.0` (пин в requirements). Прогон: контрактные тесты
S22-001 (68 операций, 92 схемы — breaking-изменений нет, обновлены только
косметические `format`/`contentMediaType`/`ValidationError.ctx`), полный
pytest **367 passed + 1 skipped**, e2e 12/12. Единственное поведенческое
изменение — отсутствие `Authorization` теперь даёт **401** вместо 403
(RFC 7235 в Starlette 1.x): тест `test_access_matrix` и SPEC §7 обновлены.
`pip-audit` — без `--ignore-vuln` («No known vulnerabilities found»).

**Создано:** 2026-10-30 (S20-001) · **Закрыто:** 2026-10-31 (спринт 22, S22-002)

---

### KI-016 · Resolved · Low · dev-deps · pytest 8.3.3 → 9.2.0

**Описание:** `pytest 8.3.3` — PYSEC-2026-1845 (moderate, UNIX tmpdir);
зависимость только для разработки/CI.

**Решение (S22-003):** `pytest 9.2.0`, `pytest-asyncio 1.4.1`,
`pytest-cov 7.1.0`, `pytest-env 1.8.3`; конфиг `pyproject.toml` менять не
потребовалось (`asyncio_mode`, `asyncio_default_fixture_loop_scope`,
`testpaths` — без предупреждений об устаревших опциях). Полный прогон —
367 passed + 1 skipped; `pip check` — OK; `pip-audit` — без игноров.
`filterwarnings = error` намеренно не включён: в коде ~1 400 предупреждений
`datetime.utcnow()`, это отдельная чистка (см. отчёт спринта 22).

**Создано:** 2026-10-30 (S20-001) · **Закрыто:** 2026-10-31 (спринт 22, S22-003)

---

### KI-019 · Resolved · Critical · deps/security · python-jose и PyJWT 2.10.0

**Описание:** аудит backend (`pip-audit`, Docker/CI-путь) показал 66 записей
уязвимостей в 7 пакетах, в т.ч. critical в `python-jose 3.3.0`
(GHSA-6c5p-j8vq-pqhj, GHSA-3qf3-8w2g-rqmx — algorithm confusion) и 24 записи
в `PyJWT 2.10.0`; `python-multipart 0.0.17` — 14 записей.

**Решение (S20-001):** `python-jose` удалён вместе с транзитивными `ecdsa`/
`rsa`; JWT-код (`app/core/security.py`) переведён на **PyJWT 2.15.1**
(все известные GHSA закрыты в 2.14.0/2.15.0), `python-multipart` →
**0.0.31**. Проверки: `pip-audit` — 0 находок по этим пакетам; функциональный
smoke JWT (access/refresh round-trip, expired/forged → None), Form-разбор,
`docker build` — успешно. В отчёте аудита остались 16 записей в 2 пакетах
(starlette, dev pytest) — см. KI-015/KI-016.

**Создано:** 2026-10-30 · **Закрыто:** 2026-10-30 (спринт 20, S20-001)

---

### KI-020 · Resolved · Critical · frontend dev-deps · vitest/tinypool

**Описание:** `pnpm audit` — 5 уязвимостей в dev-зависимостях тестового
toolchain: 2 critical (`tinypool` GHSA-5gmw-xhrv-c9v3, GHSA-85c8-ppgw-ccpr)
и 3 moderate (`vitest`/`@vitest/mocker`); в production-бандл не попадают.

**Решение (S20-001):** `vitest` и `@vitest/coverage-v8` 3.2.7 → **4.1.12**
(`tinypool` ≥2.1.2); конфиги менять не потребовалось; `vitest-axe`
совместим. Проверки: typecheck/lint/test **80/80**/build — зелёные,
`pnpm audit` — **No known vulnerabilities found**.

**Создано:** 2026-10-30 · **Закрыто:** 2026-10-30 (спринт 20, S20-001)

---

### KI-021 · Resolved · High · песочница · RestrictedPython 7.4 (3 обхода)

**Описание:** `restrictedpython 7.4` — 3 high-обхода песочницы:
GHSA-gmj9-h825-chq2 (`try/except*` type confusion, fix 8.0),
GHSA-ffg3-p8fm-mjx2 (shadowing guard-хуков, fix 8.3),
GHSA-hp3v-5vw7-fx9w (`string.Formatter` field resolution, fix 8.4).

**Решение (S20-001b):** апгрейд **7.4 → 8.5** (wheel получен через Docker,
т.к. PyPI с хоста заблокирован — KI-017). В `executor.py` добавлена
friendly-обработка новых запретов (`RestrictedFeatureError` + подсказка
f-строки/`%`); тесты: `test_executor.py` +2, `test_sandbox_limits.py` +3
(атаки `format`/`format_map`/`string.Formatter`, dunder в f-строке);
focused-прогон executor/sandbox — 39 passed, sandbox/executor/runner/
code-api/concurrency — 55 passed. Из CI `pip-audit --ignore-vuln` убраны
PYSEC-2026-1874/3917/4161. Побочный эффект — KI-018.

**Создано:** 2026-10-30 · **Закрыто:** 2026-10-30 (спринт 20, S20-001b)

---

### KI-008 · Resolved · Med · services/llm, QA · нет проверки реальных ответов LLM

**Описание:** Провайдеры DeepSeek и LM Studio покрыты тестами только на уровне
фабрики: реальные вызовы не выполнялись, потому что не было API-ключа DeepSeek
и не был запущен LM Studio. Качество и «дисциплина» ответов по уровням
(базовый не должен давать готовый код) на живой модели не проверены.

**Решение:** 2026-10-29 выполнен живой прогон
`backend/scripts/run_llm_eval.py --provider deepseek` (Q1–Q5 × 3 уровня),
ответы и оценки — в `docs/reports/llm-eval/2026-10-29/` (`REVIEW.md`,
`SUMMARY.md`). Взвешенные баллы: basic **0.99**, intermediate **0.93**,
advanced **0.96** (порог 0.75); базовый уровень — 0 нарушений политики.
Найдено одно нарушение `intermediate/Q2` (полная программа) — промпт
уточнён и поднят до v2, целевой ответ проверен (`Q2-prompt-v2.md`).
LM Studio (`qwen/qwen3-4b-2507`, порт 8034) проверен как fallback.

**Создано:** 2026-10-29 · **Закрыто:** 2026-10-29 (спринт 13)

---

### KI-009 · Resolved · Med · core/executor · лимит памяти не enforced

**Описание:** `EXECUTOR_MEMORY_LIMIT=128` МБ хранится в настройках, но не
применяется: модуль `resource` недоступен на Windows, а `subprocess` не умеет
ограничивать RSS кроссплатформенно.

**Решение:** лимит ставится в дочернем интерпретаторе
(`app/core/sandbox_limits.py`): `resource.setrlimit(RLIMIT_AS)` на POSIX и
Job Object с `JOB_OBJECT_LIMIT_PROCESS_MEMORY` на Windows. Процесс назначает
себя в job сам, поэтому гонки с запуском кода нет. `EXECUTOR_MEMORY_LIMIT`
подхватывается, признак `memory_limit_enforced` возвращается в результате.
Тесты `test_executor_memory.py`: аллокация `[0] * 10**9` даёт `MemoryError`,
процесс API жив; проверено на Windows и в Linux-контейнере.

**Создано:** 2026-10-29 · **Закрыто:** 2026-10-29 (спринт 13)

---

### KI-010 · Resolved · Low · db/seed · задачи наполняются вручную

**Описание:** Учебные задачи добавлялись только скриптом
`backend/scripts/seed_tasks.py`; в Docker-развёртывании задачи не появлялись
автоматически, `/api/v1/tasks` на чистой базе был пуст.

**Решение:** данные вынесены в `app/data/seed_tasks.py`, идемпотентный
`app/services/seed_service.seed_tasks`; при `SEED_ON_START=true` seed выполняется
в `lifespan` до приёма запросов (ошибка не валит старт, лог `seed_failed`).
Docker Compose включает флаг по умолчанию, CLI использует тот же сервис.

**Создано:** 2026-10-29 · **Закрыто:** 2026-10-29 (спринт 14)

---

### KI-013 · Resolved · Low · frontend/code-editor · Monaco грузится с CDN

**Описание:** `@monaco-editor/react` подгружал Monaco с `cdn.jsdelivr.net`;
в офлайн-развёртывании редактор не загружался.

**Решение:** пакет `@monaco-editor/react` удалён, `monaco-editor` установлен;
AMD-ассеты `min/vs` копируются в `public/monaco/vs` перед сборкой
(`scripts/copy-monaco.mjs`), `MonacoEditor` грузится lazy-чанком и работает
с локального origin. `pnpm test:offline` проверяет, что в бандле и `index.html`
нет CDN-ссылок. Спринт 19, S19-001.

**Создано:** 2026-10-29 · **Закрыто:** 2026-10-29 (спринт 19, S19-001)

---

### KI-001 · Resolved · Med · docker, config, docs · порты, занятые чужими контейнерами

**Описание:** `5432` и `6379` на машине разработки заняты другими проектами;
наши контейнеры не публиковали порты, подключение уходило в чужую БД.

**Решение:** внешние порты параметризованы (`POSTGRES_PORT`, `REDIS_PORT`);
добавлен `backend/scripts/check_ports.py`, который проверяет доступность,
«свои» таблицы и (с `--docker`) публикацию портов нашими контейнерами.
Процедура смены порта описана в RULES §11.2. Канон восстанавливается при
освобождении портов без изменения кода.

**Создано:** 2026-10-29 · **Закрыто:** 2026-10-29 (спринт 11)

---

### KI-002 · Resolved · Low · docs, ci · нет автотеста расхождения моделей и миграций

**Описание:** Тестовая схема создавалась через `create_all`, рабочая — через
Alembic; расхождения не ловились (так прошёл баг enum, KI-004).

**Решение:** `backend/tests/test_migrations.py` (маркер `migrations`):
upgrade на пустую БД, сверка колонок с `Base.metadata`, цикл
downgrade → upgrade, проверка единственной головы Alembic. Плюс `alembic check`
в CI.

**Создано:** 2026-10-29 · **Закрыто:** 2026-10-29 (спринт 11)

---

### KI-006 · Resolved · Low · api/websocket, tests · нет интеграционного теста стриминга

**Описание:** WS-стриминг проверялся только на отказе авторизации.

**Решение:** протокол вынесен в `serve_chat_socket` с интерфейсом
`WebSocketLike`; эндпоинт получает сессию через `Depends(get_db)` и провайдера
через `Depends(get_llm_provider)`. `tests/test_websocket_stream.py` проверяет
полный цикл `start → token… → done`, сохранение ответа в БД, ping/pong,
не-JSON, неизвестный тип и падение провайдера.

**Создано:** 2026-10-29 · **Закрыто:** 2026-10-29 (спринт 11)

---

### KI-007 · Resolved · Med · core/rate_limiter, main · middleware не подключён

**Описание:** Лимиты были реализованы, но не применялись.

**Решение:** `app/db/redis.py` (ленивый клиент, ping, закрытие в `lifespan`),
`RateLimitMiddleware` зарегистрирован в `main.py`, fail-open при недоступном
Redis, флаг `RATE_LIMIT_ENABLED`. `tests/test_rate_limit.py` (10 тестов) на
in-memory фейке: 429 после лимита, `Retry-After`, освобождение health,
отключение флагом, fail-open.

**Создано:** 2026-10-29 · **Закрыто:** 2026-10-29 (спринт 11)

---

### KI-012 · Resolved · Low · frontend · нет e2e-тестов

**Описание:** Отсутствовали сквозные тесты «браузер → backend → БД».

**Решение:** Playwright (`frontend/e2e/`, 12 сценариев): регистрация/вход/
выход, защищённые маршруты, песочница (безопасный код, опасный импорт, ошибка),
задачи (список, решение, подсказки), чат (стриминг, уровень), запрет админки.
Backend поднимается на отдельной БД `ai_teacher_e2e` с провайдером `echo`,
тесты изолированы уникальными пользователями. Job `e2e` в CI.

**Побочный результат:** найден и исправлен баг — после перезагрузки страницы
`loadMe()` не вызывался, и защищённые страницы показывали вечный Spinner.

**Создано:** 2026-10-29 · **Закрыто:** 2026-10-29 (спринт 11)

---

### KI-003 · Resolved · High · docker · образ PostgreSQL с pgvector

**Описание:** `postgres:17-alpine` не содержит расширения `vector`.

**Решение:** образ `pgvector/pgvector:pg17`; в `downgrade` расширение не
удаляется (RULES §11.5).

**Создано:** 2026-10-29 · **Закрыто:** 2026-10-29 (спринт 2)

---

### KI-004 · Resolved · High · models, db · enum хранил имена вместо значений

**Описание:** SQLAlchemy `Enum(UserRole)` писал `STUDENT`, в БД тип создан со
значениями `student` → ошибка вставки, HTTP 500 на регистрации.

**Решение:** `values_callable=lambda enum_cls: [e.value for e in enum_cls]` во
всех enum-колонках; регрессионные тесты.

**Создано:** 2026-10-29 · **Закрыто:** 2026-10-29 (спринт 3)

---

### KI-005 · Resolved · High · core/security, deps · passlib несовместим с bcrypt 5.x

**Описание:** `passlib 1.7.4` падал с `ValueError` на 72+ байтах.

**Решение:** passlib удалён, хэширование напрямую через `bcrypt`; длина пароля
ограничена 72 байтами в Pydantic-схеме.

**Создано:** 2026-10-29 · **Закрыто:** 2026-10-29 (спринт 3)

---

### KI-011 · Resolved · Critical · api/auth · эскалация роли при регистрации

**Описание:** `POST /auth/register` принимал `role`, любой мог стать админом.

**Решение:** регистрация всегда создаёт `student`; роль меняет только админ.

**Создано:** 2026-10-29 · **Закрыто:** 2026-10-29 (спринт 7)

---

## Легенда

- **Critical** — блокирует весь проект
- **High** — блокирует текущий спринт
- **Med** — блокирует одну задачу
- **Low** — не блокирует, но стоит починить
