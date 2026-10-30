# SECURITY_AUDIT — спринт 20 (S20-001, S20-002, S20-004)

**Дата:** 2026-10-30 · **Автор:** security-audit · **Статус:** выполнено,
остаточные риски задокументированы (см. §8).

**Окружение:** Windows 11, Python 3.11.8 (`backend/venv`), Node 24 / pnpm 12,
Docker Desktop (postgres `pgvector/pgvector:pg17` 127.0.0.1:5434, redis 6381),
git `main` + незакоммиченные изменения (S20 + незавершённый S19 perf-backend).

**Факт про сеть (важно):** PyPI с хоста заблокирован (connection reset), но
**Docker-контейнеры PyPI видят** — проверено. Поэтому аудит backend выполнен
двумя способами:
1. `pip-audit` в контейнере `python:3.12-slim` — авторитетная проверка
   (так же будет работать CI);
2. `backend/scripts/audit_python_deps.py` — офлайн-инструмент для хоста,
   использующий GitHub Advisory API (лимит 60 запросов/час), с кэшем и
   `--resume`.

---

## 1. Итоги (TL;DR)

| Область | До | После |
|---------|----|-------|
| Frontend (`pnpm audit`) | 5 уязвимостей (2 critical + 3 moderate) | **0** |
| Backend (`pip-audit -r requirements.txt`) | **66** записей в **7** пакетах (включая critical-уязвимости `python-jose` и `PyJWT`) | **16** записей в **2** пакетах (0 critical; 2 high — `starlette` PYSEC-2026-161/248, транзитивно от `fastapi 0.115.5`, векторы в приложении не используются; остальное — medium/low `starlette` и dev-only `pytest`) |
| python-jose | 3.3.0, 2 critical + 1 moderate | удалён; JWT переведён на PyJWT 2.15.1 |
| Секреты в git | — | 0 утечек в 42 коммитах (gitleaks 8.30.1), конфиг в CI |
| nginx security headers | нет | CSP + 5 заголовков, проверено `nginx -t` и Playwright |
| Бэкапы БД | нет | `scripts/backup.sh` / `restore.sh` + smoke-проверка |
| CI/Dependabot | нет security job | job `Security` (pip-audit, gitleaks, pnpm audit) + `dependabot.yml` |

**Закрыто:** 50 записей уязвимостей, 5 пакетов очищены:
`python-jose`, `ecdsa` (его зависимость), `pyjwt` 2.10.0→2.15.1,
`python-multipart` 0.0.17→0.0.31, `restrictedpython` 7.4→8.5 (S20-001b —
3 high-обхода песочницы).

---

## 2. S20-001. Frontend (`pnpm audit`)

### До

```
2 critical: tinypool — GHSA-5gmw-xhrv-c9v3 (<=2.1.0), GHSA-85c8-ppgw-ccpr (<2.1.2)
3 moderate: vitest / @vitest/mocker — GHSA-82fw-gwwq-j7x9 (<4.1.11),
            GHSA-qxg6-89mg-rqv8 (<4.1.12)
Пути: vitest, @vitest/coverage-v8, vitest-axe → vitest → tinypool/@vitest/mocker
```

Все 5 — dev-зависимости (тестовый toolchain), в production-бандл не попадают.

### Что сделано

- `vitest` 3.2.7 → **4.1.12**, `@vitest/coverage-v8` 3.2.7 → **4.1.12**;
  `tinypool` в 4.1.12 подтянут ≥2.1.2.
- `vitest-axe` 0.1.0 — последняя версия (peer `vitest >=0.16`), совместим с
  vitest 4; проверен тестом `src/test/a11y.test.tsx`.
- Конфиги `vite.config.ts` / `tsconfig.*` менять не потребовалось (секция
  `test` из `vitest/config`, coverage thresholds и exclude работают в v4).

### Проверки (после обновления)

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Типы | `pnpm typecheck` | OK |
| Линт | `pnpm lint` | OK |
| Тесты | `pnpm test` | **80/80 passed** (13 файлов) |
| Сборка | `pnpm build` | OK, `dist/` собран |
| Аудит | `pnpm audit` | **No known vulnerabilities found**, exit 0 |

---

## 3. S20-001. Backend

### 3.1 Инструмент для хоста: `backend/scripts/audit_python_deps.py`

Зачем: `pip-audit` с хоста установить нельзя (PyPI заблокирован), а аудит
нужен и разработчику. Скрипт:

- скачивает глобальные advisory `GET https://api.github.com/advisories?ecosystem=pip`
  (cursor-пагинация `Link: rel="next"`, `User-Agent`, без токена);
- сопоставляет с `pip list --format=json` (PEP 503-нормализация имён,
  сравнение версий через `packaging`, диапазоны `>=, >, <, <=, =` через
  запятую), пропускает withdrawn-записи;
- печатает таблицу + summary, `--json-out`, коды возврата: `0` — чисто,
  `1` — есть находки ≥ `--fail-on` (default `high`), `2` — аудит не выполнен;
- уважает лимит GitHub API (60/час): кэш в `%TEMP%/ai-teacher-audit`
  (TTL `--cache-ttl-hours`, default 24), при исчерпании лимита сохраняет
  курсор и предупреждает; `--resume` продолжает скачивание, `--offline` —
  только кэш, `--installed-json` — аудит по сохранённому `pip list`.

Прогон на хосте (до фикса): найдено `critical=3, high=19, moderate=21, low=8`,
exit 1; в т.ч. `python-jose 3.3.0` — GHSA-6c5p-j8vq-pqhj (critical),
GHSA-3qf3-8w2g-rqmx (critical), GHSA-cjwg-qfpm-7377. Данные GitHub API были
неполными (лимит 60 запросов/час, 6000 advisory), поэтому **авторитетный**
результат ниже — `pip-audit` в контейнере.

Контрольный прогон после фикса: квота GitHub API была уже исчерпана
(осталось 2 запроса) — скрипт корректно обработал лимит: скачал 200 advisory,
вывел предупреждение, сохранил курсор для `--resume` и вернул exit 2
(«аудит неполный») — то есть не выдал ложное «чисто». Это ожидаемое
поведение; полный результат даёт `pip-audit` (§3.2).

ruff по скрипту: `All checks passed`.

### 3.2 Авторитетный аудит: `pip-audit` в Docker

Команда (контейнер видит PyPI):

```bash
docker run --rm -v "C:/Projects/AI/ai-teacher_python/backend:/repo:ro" \
  python:3.12-slim sh -c \
  "pip install -q pip-audit && pip-audit -r /repo/requirements.txt -f json -o /work/pip-audit.json"
```

Результаты по `requirements.txt` (CI-путь — резолвинг зависимостей с PyPI):

| Пакет (до) | Записей | Уникальных ID | Фикс |
|------------|---------|---------------|------|
| `python-jose` 3.3.0 | 6 | PYSEC-2024-232, PYSEC-2024-233, PYSEC-2025-185, PYSEC-2026-4298 | 3.4.0 / нет (3qf3) |
| `ecdsa` 0.19.2 (транзитивно от jose) | 2 | PYSEC-2026-1325 | нет (upstream out of scope) |
| `pyjwt` 2.10.0 | 24 | GHSA-pxh4-856f-4h89, PYSEC-2025-183, PYSEC-2026-120/175/176/177/178/179/1814/4140/4141/4144/4145/4147/4148/4149/4152/4183 | 2.14.0 / 2.15.0 |
| `python-multipart` 0.0.17 | 14 | PYSEC-2026-1851/1852/3036/3037/3038/3039/3040 | 0.0.22 … 0.0.31 |
| `restrictedpython` 7.4 | 4 | PYSEC-2026-1874/3917/4161 | 8.0 / 8.3 / 8.4 |
| `starlette` 0.41.3 (транзитивно от fastapi 0.115.5) | 14 | PYSEC-2026-161/1941/1942/2280/2281/248/249 | 0.47.2 … 1.3.1 |
| `pytest` 8.3.3 (dev) | 2 | PYSEC-2026-1845 | 9.0.3 |

**Итого до: 66 записей в 7 пакетах.**

**После изменений: 16 записей в 2 пакетах** (8 уникальных ID):

| Пакет | Записей | ID | Severity (по OSV/GitHub) | Почему не исправлено сейчас |
|-------|---------|----|--------------------------|------------------------------|
| `starlette` 0.41.3 (транзитивно от fastapi 0.115.5) | 14 | PYSEC-2026-161/1941/1942/2280/2281/248/249 | 2 high + 3 medium + 2 low | фикс в starlette ≥1.3.1 требует координированного апгрейда FastAPI (0.162+ тянет opentelemetry и меняет совместимость) — KI-015, принятый риск; векторы в приложении не используются (см. §8.2) |
| `pytest` 8.3.3 (dev) | 2 | PYSEC-2026-1845 | medium (dev-only, UNIX tmpdir) | мажорный 9.x, dev-зависимость, не в runtime — KI-016 |

`python-jose`, `ecdsa`, `pyjwt`, `python-multipart`, `restrictedpython`
после изменений — **0 находок**. RestrictedPython обновлён до 8.5 в S20-001b
(Lead), его PYSEC-2026-1874/3917/4161 из игнора убраны.

### 3.3 Удаление python-jose → PyJWT

`python-jose` использовался в одном месте: `app/core/security.py`
(`from jose import jwt`; encode/decode). Изменения:

- `requirements.txt`: `python-jose[cryptography]==3.3.0` удалён,
  `pyjwt==2.10.0` → **`pyjwt==2.15.1`** (все известные GHSA PyJWT закрыты в
  2.14.0/2.15.0; 2.15.1 — последняя на PyPI на 2026-10-30, проверено
  `pip index versions pyjwt` в контейнере);
- `python-multipart==0.0.17` → **`0.0.31`** (закрыты GHSA-wp53-j4wj-2cfg,
  GHSA-pp6c-gr5w-3c5g, GHSA-5rvq-cxj2-64vf, GHSA-v9pg-7xvm-68hf);
- `app/core/security.py`: `from jose import jwt` → `import jwt`,
  `except jwt.JWTError` → `except jwt.PyJWTError`. API совпадает:
  `jwt.encode(payload, key, algorithm=...)`, `jwt.decode(token, key, algorithms=[...])`.

Почему это безопасно проверить без pytest (pytest в это время занят
perf-backend'ом, KI-014/одна тестовая БД):

1. Пин-версии **проверены на существование** (`pip index versions` в
   `python:3.12-slim`): `pyjwt 2.15.1`, `python-multipart 0.0.31`.
2. Скачаны и установлены локально (Docker-контейнер имеет PyPI):
   `pip download --no-deps` → `pip install --no-index --find-links .wheelhouse
   pyjwt==2.15.1 python-multipart==0.0.31`; `.wheelhouse` удалён.
   Установлено: `PyJWT 2.15.1`, `python-multipart 0.0.31`; `pip check` —
   «No broken requirements found».
3. Функциональная проверка без БД (скрипт, не pytest):
   - `import app.main` — OK;
   - access/refresh round-trip, `type`/`sub`/`exp` в payload — OK;
   - просроченный токен, мусор, `a.b.c`, токен с чужой подписью → `None`
     (401-путь) — OK;
   - bcrypt hash/verify — OK;
   - FastAPI `Form` разбор с python-multipart 0.0.31 (ASGITransport) — OK.
4. `docker build -t ai-teacher-backend:audit ./backend` — **успешно** (CI-путь):
   в образе `pyjwt-2.15.1`, `python-multipart-0.0.31`, `python-jose`/`ecdsa`/`rsa`
   отсутствуют; `starlette-0.41.3`, `restrictedpython-7.4` — как в аудите.

Локальная версия Python в venv — 3.11.8; CI собирает на 3.12, Docker-образ —
`python:3.12-slim` (сборка успешна). Полный прогон pytest — за Lead
(perf-backend владеет тестовой БД в S19); риск: PyJWT 2.15.1 мог ужесточить
валидацию токенов, но затронутые пути покрыты функциональной проверкой.

### 3.4 Пин и проверка версий

| Пин | Существует | Установлен локально | Проверен |
|-----|-----------|---------------------|----------|
| `pyjwt==2.15.1` | да (`pip index versions`) | да | round-trip/expired/forged; CI build |
| `python-multipart==0.0.31` | да | да | FastAPI Form smoke; CI build |

`requirements.txt` больше не содержит `python-jose`; остальные пины не
менялись.

---

## 4. S20-002. Секреты и конфигурация

### 4.1 `.env` и `.gitignore`

- `.gitignore` содержит `.env`, `.env.local`, `.env.*.local` — проверено.
- `backups/` добавлен в `.gitignore` (дампы содержат email/персональные
  данные, S20-004).
- Значения `.env` не читались и не печатались; проверено только наличие
  ключей в `.env.example` (все — placeholders `change_me_*`, `your_*_here`).

### 4.2 gitleaks

- Добавлен `.gitleaks.toml`: `[extend] useDefault = true` (встроенные правила)
  + project-правила `deepseek-api-key` (`sk-…`), `postgres-password-in-url`,
  `jwt-secret-assignment`; allowlist — только placeholders из
  `.env.example`/`Design.md` §10.2 и тестовые значения CI, пути
  `node_modules`, `venv`, `dist`.
- Инструмент: gitleaks **8.30.1** (скачан с GitHub Releases, локальная
  проверка конфига).
- **Скан истории:** `gitleaks git . --config .gitleaks.toml --redact --verbose`
  → `42 commits scanned`, **no leaks found**, exit 0.
- **Негативный контроль (правила реально ловят):** в temp-файл положены
  фейковые `sk-…`, `postgresql://user:pass@host/db`, `SECRET_KEY=…` → найдены
  все **3** правила (`deepseek-api-key`, `postgres-password-in-url`,
  `jwt-secret-assignment`); файл-пример с placeholders `change_me_*`/`your_*_here`
  не сработал (allowlist OK).
- Найденный при первом прогоне `DATABASE_URL=postgresql://ai_teacher:secure_password_here@…`
  в `Design.md` — документационный placeholder (`secure_password_here`), внесён
  в allowlist; реального секрета нет.

### 4.3 `docker-compose.prod.yml`

- `POSTGRES_PASSWORD`, `SECRET_KEY` — `:?set …` (compose падает без переменной,
  дефолтных паролей нет); `DEBUG: "false"`; порты БД/Redis наружу не
  публикуются; наружу только frontend (`HTTP_PORT`).
- CORS: `ALLOWED_ORIGINS` добавлен как ENV-переменная (не `*`); в
  `app/config.py` default — только `localhost:3000`/`127.0.0.1:3000`.
- Секретов в файле нет.

---

## 5. S20-002. nginx security headers (frontend/nginx.conf)

Добавлены на уровне `server` (nginx наследует их в `location` без
собственных `add_header`; поэтому `add_header` из `/assets/` убран —
`expires 1y` даёт тот же кэш, а наследование заголовков сохраняется):

| Заголовок | Значение |
|-----------|----------|
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; worker-src 'self' blob:; child-src 'self' blob:; frame-ancestors 'none'; frame-src 'none'; object-src 'none'; base-uri 'self'; form-action 'self'; manifest-src 'self'` |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | camera/microphone/geolocation/payment/usb/… = `()`, `browsing-topics=()` |
| `Strict-Transport-Security` | `max-age=31536000` (действует только при HTTPS) |
| `server_tokens` | `off` |

Обоснование CSP: Vite собирает только внешние хэшированные бандлы (в
`dist/index.html` нет inline-скриптов); Monaco работает с локальных
`/monaco/vs` (KI-013), worker'ы — `blob:`; `style-src 'unsafe-inline'` нужен
React/Tailwind/Monaco для style-атрибутов; `connect-src 'self'` покрывает
`/api` и WebSocket того же origin. Дополнительно `index.html` отдаётся с
`Cache-Control: no-cache`.

### Проверки

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Синтаксис | `docker run --rm -v ...nginx.conf:/etc/nginx/conf.d/default.conf nginx:1.27-alpine nginx -t` | `syntax is ok`, test successful |
| Заголовки живьём | nginx 1.27-alpine + curl/Playwright | все 6 заголовков присутствуют; CSP совпадает с конфигом |
| SPA fallback | `GET /some/spa/route` | 200, отдан `index.html` |
| `/index.html` | `Cache-Control` | `no-cache` |
| CSP + Monaco | Playwright: AMD-loader `vs/editor/editor.main` под CSP | **MONACO_LOADED: true**, `MONACO_ERROR: null`, 0 console errors (`unsafe-eval` не потребовался) |

Контейнер теста поднимался временно (`ai_teacher_nginx_csp_test`) и удалён;
docker-compose сервисы не трогались.

---

## 6. CI и Dependabot

### `.github/workflows/ci.yml` — новый job `Security`

1. `pip-audit -r backend/requirements.txt --strict --desc` + `--ignore-vuln`
   для 8 известных остаточных ID (7 starlette + 1 dev pytest, см. §8) —
   чтобы job был зелёным и ловил **новые** уязвимости; после апгрейда
   fastapi/starlette и pytest ignores убрать. RestrictedPython-игноры
   удалены после S20-001b. Команда с текущим списком прогнана в контейнере
   `python:3.12-slim` против обновлённого `requirements.txt`:
   `No known vulnerabilities found, 16 ignored` → exit 0 (тот же результат
   будет на GitHub Runner'е, где PyPI доступен).
2. gitleaks 8.30.1: скачивание с `checksums.txt` + `sha256sum -c`,
   `gitleaks git . --config .gitleaks.toml --redact --verbose`
   (`fetch-depth: 0` — скан всей истории).
3. `pnpm audit --audit-level=high` (dev-only moderate не блокируют).

YAML проверен `yaml.safe_load` (CI + dependabot); локально job не запускается
(KI-014 — Actions billing). Команда pip-audit с ignore-списком прогнана в
контейнере против `requirements.txt` — см. §7.

### `.github/dependabot.yml`

- `pip` (`/backend`) + `npm` (`/frontend`) + `github-actions` (`/`),
  weekly (Mon 06:00 Europe/Moscow), лимит 5 PR, группы minor/patch,
  conventional-commit префиксы.

---

## 7. S20-004. Бэкапы и восстановление

Файлы: `scripts/backup.sh`, `scripts/restore.sh` (bash; на Windows — Git Bash).
Документация: `docs/GETTING_STARTED.md` §8, `docs/DESIGN_ADMIN_AND_OPS.md` §6.

### Smoke-проверка (2026-10-30, dev-БД `ai_teacher`)

```bash
bash scripts/backup.sh -o <tmp>/backups
#   -> ai_teacher_20261030T075746Z.dump.gz (8.8 kB) + .sha256
#   -> "Проверка архива: pg_restore -l OK"

bash scripts/restore.sh -f <dump> -t ai_teacher_restore_check --create -y --verify
```

| Проверка | Результат |
|----------|-----------|
| Таблиц в источнике / восстановлено | 14 / **14** |
| users | 5 / **5** |
| tasks | 6 / **6** |
| chat_sessions / chat_messages | 2 / 2 — **совпало** |
| code_executions | 2 / **2** |
| alembic_version | `010` |
| Здоровье архива | `pg_restore -l` OK, `gzip -t` OK |
| Retention | тестовый бэкап с mtime −40 дней удалён при `-r 14`, свежие сохранены |
| Guard «рабочая БД» | `-t ai_teacher` без `--force` → exit 2, отказ |
| Guard «нет БД» | несуществующая цель без `--create` → exit 1, понятная ошибка |
| Cleanup | `ai_teacher_restore_check` удалён (`dropdb`), 0 записей в `pg_database` |

Скрипты используют `docker exec ai_teacher_postgres pg_dump -Fc | gzip`
(локальный `pg_dump` не нужен), проверяют, что контейнер запущен (KI-001),
пишут sha256, `restore.sh` по умолчанию восстанавливает в scratch-БД и
требует подтверждения.

---

## 8. Остаточные риски и что делать (для Lead / KI)

1. **`restrictedpython 7.4` — 3 high — ✅ ЗАКРЫТО (S20-001b, Lead).**
   PYSEC-2026-1874/3917/4161 (bypass sandbox через `try/except*`,
   positional-only hooks, `string.Formatter`). Библиотека обновлена **7.4 → 8.5**
   (пин в `requirements.txt`), прогнаны все тесты песочницы
   (`test_executor*`, `test_sandbox_limits`, `test_runner`, `test_code_api`,
   `test_executor_concurrency` — 55 passed) + добавлены регрессионные тесты
   на новые векторы. Побочный эффект 8.x: `str.format`/`format_map`/
   `string.Formatter` запрещены целиком (это и есть фикс); ученику теперь
   возвращается `RestrictedFeatureError` с подсказкой про f-строки и `%`.
   Из CI-игнора убраны PYSEC-2026-1874/3917/4161.
2. **`starlette 0.41.3` — 7 ID (2 high, 3 medium, 2 low)** — принятый риск
   (KI-015). Транзитивная от `fastapi==0.115.5`; исправление в starlette 1.x
   требует координированного апгрейда FastAPI (0.162+ тянет opentelemetry и
   ломает совместимость). Векторы в приложении **не достижимы**:
   - `StaticFiles`/`FileResponse` (Range/DoS, UNC/SSRF) — файлы отдаёт nginx,
     в API этих классов нет;
   - `HTTPEndpoint` dispatch — не используем `HTTPEndpoint`;
   - Host/path-инъекции (PYSEC-2026-161/248) — влияют на `request.url`, а
     авторизация строится на роутере и зависимостях, не на `request.url`;
     `request.url.path` используется только в логах и ключе rate-limit;
   - `request.form()` urlencoded-лимиты — API принимает JSON, формы только
     multipart с `UploadFile` (импорт задач, teacher/admin).
   План: Dependabot PR + апгрейд fastapi/starlette в v0.3.0 с полным прогоном.
3. **`pytest 8.3.3` — 1 moderate (dev-only, UNIX tmpdir)** — KI-016.
   Не в runtime; фикс в pytest 9.0.3 появится вместе с dev-апгрейдом.
4. **Локальный venv**: после S20-001b все пины (PyJWT 2.15.1,
   python-multipart 0.0.31, RestrictedPython 8.5) установлены и проверены
   локально; `starlette`/`pytest` остались прежними, полный прогон — Lead.
5. **`pip-audit` ignores в CI** (8 ID для starlette + dev pytest) — временные,
   обоснованы в KI-015/KI-016; убрать после апгрейда fastapi/starlette и
   pytest. Если ID исчезнут из базы — pip-audit просто не найдёт их в игноре.
6. **GitHub Advisory API — 60 запросов/час**: локальный скрипт при полном
   прогоне сохраняет неполные данные (partial) и требует `--resume`; это
   документировано в шапке скрипта. В CI используется `pip-audit`.
7. **Аудит frontend — только `pnpm audit`**: `pnpm audit` использует npm
   registry; lockfile проверен. Supply-chain правила pnpm
   (`allowBuilds: [esbuild]`) не расширялись.

---

## 9. Проверки (сводка команд)

| # | Проверка | Команда | Результат |
|---|----------|---------|-----------|
| 1 | Frontend audit до/после | `pnpm --dir frontend audit` | 5 → 0 |
| 2 | Frontend quality | `pnpm typecheck && lint && test && build && test:offline && pnpm audit` | OK, 80/80, 0 vulns, entry 78.71 kB |
| 3 | Backend audit (CI-путь) | `pip-audit -r backend/requirements.txt` в `python:3.12-slim` | 66 → **16** (2 пакета) |
| 4 | CI-команда с ignores | тот же pip-audit + 8 `--ignore-vuln` | см. §6 (прогон в контейнере) |
| 5 | Импорт приложения | `python -c "import app.main"` (venv) | OK |
| 6 | JWT/multipart smoke | скрипт из §3.3 | OK (5 сценариев + Form) |
| 7 | Локальный audit-скрипт | `python scripts/audit_python_deps.py` | таблица + exit 1 на high (см. §3.1) |
| 8 | ruff | `ruff check app/core/security.py scripts/audit_python_deps.py` | 0 |
| 9 | gitleaks | `gitleaks git . --config .gitleaks.toml` | 0 утечек, 42 коммита |
| 10 | nginx | `nginx -t` (1.27-alpine) | OK |
| 11 | CSP+Monaco | Playwright | загрузился |
| 12 | Docker build | `docker build ./backend` | успешно, pyjwt 2.15.1 / multipart 0.0.31 |
| 13 | Бэкап/restore | `bash scripts/backup.sh` + `restore.sh --verify` | счётчики совпали |
| 14 | YAML | `yaml.safe_load(ci.yml, dependabot.yml)` | OK |
| 15 | RestrictedPython 8.5 (S20-001b) | `pytest tests/test_executor.py tests/test_sandbox_limits.py` | 39 passed; sandbox-набор 55 passed |
| 16 | Auth hints (S20-003) | qa-access access matrix | анонимный запрос → 401 (было 200) |

Не запускалось на момент отчёта (и почему): полный `pytest` — тестовая БД
`ai_teacher_test` принадлежала perf-backend до завершения task-1 (запускает
Lead); GitHub Actions — KI-014.

---

## 10. Изменённые файлы

**Создано:**
- `backend/scripts/audit_python_deps.py` — локальный аудит по GitHub Advisory;
- `.gitleaks.toml`, `.github/dependabot.yml`;
- `scripts/backup.sh`, `scripts/restore.sh`;
- `docs/reports/sprint-20/SECURITY_AUDIT.md` (этот файл).

**Изменено:**
- `backend/requirements.txt` — удалён python-jose, `pyjwt==2.15.1`,
  `python-multipart==0.0.31` (+ комментарии с GHSA);
- `backend/app/core/security.py` — PyJWT вместо python-jose;
- `frontend/package.json`, `frontend/pnpm-lock.yaml` — vitest/coverage 4.1.12;
- `frontend/nginx.conf` — security headers + `server_tokens off` +
  `expires`-кэш без потери наследования заголовков;
- `.github/workflows/ci.yml` — job `Security`;
- `docker-compose.prod.yml` — `ALLOWED_ORIGINS` из ENV;
- `.gitignore` — `backups/`;
- `docs/GETTING_STARTED.md` §8, `docs/DESIGN_ADMIN_AND_OPS.md` §4/§6/§7.

---

## 11. Воспроизведение

```bash
# Frontend
pnpm --dir frontend audit && pnpm --dir frontend test

# Backend audit (Docker-контейнер видит PyPI; хост — нет)
docker run --rm -v "$PWD/backend:/repo:ro" python:3.12-slim sh -c \
  "pip install -q pip-audit && pip-audit -r /repo/requirements.txt --strict --desc"

# Локальный аудит без PyPI (GitHub Advisory API, лимит 60/час)
cd backend && ./venv/Scripts/python.exe scripts/audit_python_deps.py
# продолжить неполный прогон: --resume

# Секреты
gitleaks git . --config .gitleaks.toml --redact --verbose

# nginx config
docker run --rm --add-host backend:127.0.0.1 \
  -v "$PWD/frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
  nginx:1.27-alpine nginx -t

# Бэкап/restore smoke
bash scripts/backup.sh
bash scripts/restore.sh -f backups/<file>.dump.gz -t ai_teacher_restore_check --create -y --verify
docker exec ai_teacher_postgres dropdb -U ai_teacher ai_teacher_restore_check
```
