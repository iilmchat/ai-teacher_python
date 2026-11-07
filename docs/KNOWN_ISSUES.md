# KNOWN_ISSUES.md — Реестр известных проблем

> Этот документ содержит список всех известных проблем, ограничений и блокеров.
> Каждая проблема имеет ID `KI-NNN`, статус, severity и план закрытия.

**Последнее обновление:** 2026-11-08 (спринт 45: KI-028 закрыт)  
**Всего проблем:** 30 (активных: 5, закрытых: 25)

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
С S22-004 это же ограничение закрывает авто-мерж Dependabot minor/patch: на
Free/private нет ни branch protection, ни auto-merge — группа обновлений
мержится вручную после зелёного CI.

**План закрытия:** (1) владелец выдаёт GitFlic-токен/регистрирует агент →
прогнать пилот → включить гейт и проверить красным MR; либо (2) GitHub Pro /
публичный репозиторий → `pwsh scripts/ci/protect-branch.ps1`.

**Создано:** 2026-10-30 (S21-004) · **Обновлено:** 2026-10-30

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

### KI-027 · Accepted · Low · api/auth, frontend · нет отзыва JWT: logout — no-op

**Описание:** `POST /auth/logout` ничего не делает (клиент просто забывает
токены), денлиста/`token_version` нет, JWT живут в `localStorage` (XSS-риск).
Access-токен (30 мин) после удаления аккаунта или смены пароля валиден до
истечения; refresh уже отклоняется для неактивных (KI-026).

**Workaround:** короткий `ACCESS_TOKEN_EXPIRE_MINUTES`, `is_active` как ручной
«рубильник» блокировки, удаление аккаунта анонимизирует данные.

**План (v0.4.0):** `token_version` в `users` + проверка в `get_current_user`
(инкремент при смене пароля/роли/удалении), отзыв refresh при logout.
**План (v0.5.0):** смена пароля с отзывом прочих сессий, UI списка активных
сессий и «выйти на всех устройствах» (`TODO_V0.5.md` S45-001, S45-005).
**План (v0.6.0):** перенос хранения токенов в httpOnly-cookie/BFF с
CSRF-защитой, флаг `AUTH_TOKEN_TRANSPORT` и рабочий откат
(`TODO_V0.6.md` S51-001…S51-003) — решение владельца от 2026-11-05:
перенос отложен с v0.5.0, риск XSS остаётся зафиксированным до v0.6.0.

**Создано:** 2026-11-04 · **Обновлено:** 2026-11-05 (планы v0.5.0 и v0.6.0)

---

### KI-028 · Closed · Med · api/users, frontend · нет смены пароля и управления активными сессиями

**Описание (на момент открытия):** в `api/v1/auth.py` были только
`register`/`login`/`refresh`/`logout`/`me`; эндпоинта смены пароля не было.
`users.token_version` отсутствовал, список активных сессий был недоступен,
отзыв отдельного refresh-токена невозможен. Пользователь, у которого украли
пароль, не мог его сменить без вмешательства администратора.

**Решение (v0.5.0, спринт 45):**

- миграция `018` добавила `users.token_version`; пара токенов содержит `tv`,
  refresh с устаревшей версией получает 401;
- `POST /api/v1/users/me/password` проверяет текущий пароль, хэширует bcrypt
  в потоке, пишет аудит `user.password_changed` и возвращает текущему
  устройству новую пару;
- миграция `019` добавила `user_sessions` (`jti`, user-agent, IP, время,
  отзыв); `jti` ротируется при refresh;
- `GET /users/me/sessions`, `DELETE /users/me/sessions/{id}` и
  `POST /users/me/sessions/revoke-others` («выйти на всех устройствах»);
- UI: карточки «Смена пароля» и «Активные сессии» в профиле.

**Проверки:** backend `tests/test_password_change.py` (11) и
`tests/test_sessions.py` (11); e2e `frontend/e2e/sprint45-account.spec.ts` (4).

**Создано:** 2026-11-05 · **Закрыто:** 2026-11-08

---

### KI-029 · Open · Low · models/task · `best_solution` пишется, но не читается

**Описание:** `user_task_progress.best_solution` заполняется при успешной
отправке (`app/services/task_service.py`), но ни один API его не отдаёт и ни
одна страница его не показывает. Данные хранятся без возможности
использования: учитель не может посмотреть решение ученика, ученик — своё
успешное решение. Это же блокирует разбор работ и drill-down по назначению.

**Workaround:** нет — функциональности не существует.

**План (v0.5.0):** S42-002 (таблица `task_attempts` с полной историей
попыток), S46-001 (`GET /teacher/students/{id}/attempts` — доступ только
владельцу класса), S46-003 (drill-down по назначению).

**Создано:** 2026-11-05 · **Обновлено:** 2026-11-05

---

### KI-030 · Open · Low · api/v1, frontend · часть API не покрыта интерфейсом

**Описание:** маршруты существуют и покрыты бэкенд-тестами, но не вызываются
фронтендом: `GET /admin/audit`, `GET /admin/analytics/export`, `GET
/code/history`, `POST /code/analyze`, `GET /code/limits`, `POST /tasks/generate`,
`GET /tasks/{id}/versions` (+ restore), `GET /tasks/stats`,
`GET /tasks/categories`, `GET /users/{id}`, `POST /users/me/activity`,
`PATCH /auth/me`, `DELETE /auth/me`. Для пользователя это выглядит как
«функция есть в документации, но её нет в продукте»; для владельца — как
недоказанный контракт.

**Workaround:** пользоваться API напрямую (Swagger `/api/docs`).

**План (v0.5.0):** UI для каждого маршрута — S42-004, S44-001, S44-002,
S45-002, S45-003, S47-001, S47-002, S47-003. Генерация задач через LLM
(`POST /tasks/generate`) и история версий задачи
(`GET /tasks/{id}/versions`) UI в v0.5.0 не получают — бэклог
(`TODO_V0.5.md` §9). `POST /users/me/activity` закрывается вместе с
переходом на `token_version` (v0.4.0, спринт 38) и UI активных сессий
(S45-005).

**Создано:** 2026-11-05 · **Обновлено:** 2026-11-05

---

## Закрытые проблемы

### KI-024 · Resolved · Low · core/metrics · метрики LLM/кэша считались на процесс

**Описание:** `llm_requests`, `cache_hits` и т.п. отдавались как gauge из in-memory
счётчиков процесса; при нескольких воркерах значения не суммировались.

**Решение (v0.3.3):** метрики стали событиями — `llm_requests_total{provider,model,status}`,
`llm_latency_seconds`, `llm_first_token_seconds`, `llm_tokens_total{provider,kind}`,
`llm_fallbacks_total{primary}`, `cache_*_total`; сервисы инкрементируют их в момент
события (`llm_call_observed`, `cache_observed`), а не снимают gauge при scrape.
Добавлен multiprocess-режим `prometheus_client` (`PROMETHEUS_MULTIPROC_DIR`): любая
реплика отдаёт общий агрегат, каталог чистит `docker-entrypoint.sh` перед стартом.
Пул БД остался gauge (`db_pool_connections{livesum}`, `db_pool_size{max}`) — это
состояние процесса; версия сборки — `app_build_info{version}`.
Тесты: `tests/test_metrics_export.py`.

**Создано:** 2026-11-01 · **Закрыто:** 2026-11-05 (v0.3.3)

---

### KI-026 · Resolved · Med · api/auth, core/security · неактивный аккаунт мог получить токены

**Описание (аудит v0.3.3):** `POST /auth/login` и `POST /auth/refresh` не
проверяли `users.is_active`: после `DELETE /auth/me` (анонимизация + `is_active=false`)
держатель refresh-токена получал новую пару токенов, а `logout` был no-op.
Дополнительно: `bcrypt` вызывался синхронно из async-обработчиков и блокировал
event loop на ~0.1–0.3 с; `SECRET_KEY` по умолчанию совпадал с `.env.example`;
`LoggingEmailSender` писал адрес получателя в лог открытым текстом.

**Решение:** login отклоняет неактивных (и не различает «нет такого» и
«заблокирован»), refresh проверяет `is_active`; `hash_password`/`verify_password`
выполняются в `run_in_threadpool`; при старте пишется `insecure_secret_key`,
если ключ дефолтный или короче 32 символов; email в логах маскируется
(`mask_email`). Тесты: `tests/test_auth.py` (неактивный login/refresh, refresh
после удаления аккаунта). Отзыв токенов вынесен в **KI-027**.

**Создано:** 2026-11-04 · **Закрыто:** 2026-11-05 (v0.3.3)

---

### KI-025 · Resolved · Low · scripts/apply_retention · retention запускается вручную

**Описание:** очистка по `RETENTION_*_DAYS` выполнялась скриптом/по cron, а не
самим приложением; автоматического планировщика не было — на self-hosted
установке retention легко забыть, хотя сроки хранения заявлены в PRIVACY.md.

**Решение (S32, v0.3.2):** встроенный планировщик
`app/services/scheduler.py`: одна asyncio-задача в lifespan, включается
`RETENTION_SCHEDULER_ENABLED` (в production — из `docker-compose.prod.yml`),
время запуска `RETENTION_SCHEDULER_AT` (UTC). На время прогона берётся
advisory-lock PostgreSQL (`pg_try_advisory_lock`) — при нескольких инстансах
двойного запуска нет; остановка приложения даёт доиграть текущий прогон.
Добавлены счётчики `retention_rows_deleted_total` / `retention_runs_total`
(в т.ч. для CLI). Покрыто `tests/test_scheduler.py` (18 тестов), описано в
DESIGN_ADMIN_AND_OPS §11 и PRIVACY §4. Cron остаётся альтернативой.

**Создано:** 2026-11-01 · **Закрыто:** 2026-11-03 (спринт 32, S32-001…S32-002)

---

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

### KI-017 · Resolved · Low · окружение/инструменты · PyPI недоступен с хоста

**Описание:** pypi.org/iles.pythonhosted.org с машины разработки
заблокированы (connection reset/timeout): pip install/pip-audit с хоста
не работают. Docker-контейнеры PyPI видят (нестабильно), npm registry и
pi.github.com доступны.

**Решение (S22-005, спринт 22):** офлайн-установка формализована —
scripts/wheelhouse.py: uild --out .wheelhouse --docker (скачивание всех
пинов Linux-контейнером) и install --from .wheelhouse --python
backend/venv/Scripts/python.exe (pip install --no-index --find-links). Для CI
тот же скрипт наполняет named volume i-teacher-wheelhouse
(scripts/ci/build-wheelhouse.ps1). Порядок — GETTING_STARTED §4 и RULES §11.21;
аудит — pip-audit в контейнере / ackend/scripts/audit_python_deps.py,
авторитетный результат — job Security.

**Оговорка:** сам доступ к PyPI с хоста не восстановлен — это ограничение
сети, а не проекта; основной путь остаётся CI (контейнер, зеркала, wheelhouse).

**Создано:** 2026-10-30 (S20-001) · **Закрыто:** 2026-10-31 (спринт 22, S22-005)

---
### KI-022 · Resolved · Med · performance/песочница · throughput submit (2.5 RPS → 40+ RPS)

**Описание:** нагрузочный тест S19-006: submit держал 2.5 RPS при p95
2219.7 мс (бюджет 2000 мс), knee ≈2 RPS. Причина — песочница: каждый тест-кейс
в отдельном дочернем интерпретаторе (~0.5–0.6 с старта на кейс), 3 кейса ×
EXECUTOR_MAX_CONCURRENCY=4 ≈ 2.3 submit/s.

**Решение (S23-001/S23-002):**
- батч: все кейсы задачи — один интерпретатор, построчный JSON-протокол,
  таймаут на кейс (_BATCH_RUNNER);
- пул тёплых процессов (
unner_pool.py, EXECUTOR_POOL_SIZE=2), перезапуск
  после 50 задач и после любого сбоя;
- нагрузочный гейт в CI: PR — 0.5 RPS (Perf smoke), ночь — 2 RPS
  (perf-nightly.yml).

**Результат:** submit 5 RPS — p50 34.8 мс, **p95 48.9 мс** (было 2219.7),
0 ошибок; knee не найден до 40 RPS (p95 95 мс). health 50 RPS p95 7.3 мс,
	asks 20 RPS p95 19.3 мс. Цифры — docs/reports/sprint-23/LOAD_TEST-SUBMIT.md,
docs/reports/sprint-23/load-test.json. Атакующие кейсы в батче/пуле — 36
тестов (	est_sandbox_batch_security.py), пул — 11 тестов.

**Создано:** 2026-10-30 (S19-006) · **Закрыто:** 2026-10-31 (спринт 23, S23-001/002)

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
