# Sprint 20: Security Audit & Release v0.2.0 — Отчёт

**Период:** 2026-10-30  
**Статус:** ✅ S20-001/001b/002/003/004/005 выполнены; S20-003 — 35 тестов,
IDOR не найден, F1 (LOW) исправлена; e2e — **12/12**; S20-006 — локальные
гейты, тег `v0.2.0`/push и Docker-smoke — за релиз-инженером (CI — KI-014).

**Связанные документы:**
[SECURITY_AUDIT.md](SECURITY_AUDIT.md) — детальный аудит;
[ACCESS_MATRIX.md](ACCESS_MATRIX.md) — матрица доступа (35 тестов);
[LOAD_TEST.md](../sprint-19/LOAD_TEST.md) — нагрузка S19-006;
[KNOWN_ISSUES.md](../../KNOWN_ISSUES.md) — KI-015…KI-022.

---

## 1. Файлы (+/-)

**Создано:**

```
+ .gitleaks.toml                                  — правила секретов + allowlist
+ .github/dependabot.yml                          — pip/npm/actions, weekly
+ backend/scripts/audit_python_deps.py            — офлайн-аудит по GitHub Advisory API
+ backend/tests/test_access_matrix.py             — тесты «эндпоинт × роль» (S20-003)
+ scripts/backup.sh                               — pg_dump через docker exec + gzip + sha256
+ scripts/restore.sh                              — восстановление в scratch-БД + guard
+ docs/reports/sprint-20/SECURITY_AUDIT.md        — отчёт аудита S20-001/002/004
+ docs/reports/sprint-20/ACCESS_MATRIX.md         — матрица доступа (S20-003)
+ docs/reports/sprint-20/SPRINT-20.md             — этот отчёт
```

**Изменено:**

```
~ backend/requirements.txt                       — python-jose удалён; pyjwt 2.15.1;
                                                   python-multipart 0.0.31; restrictedpython 8.5
~ backend/app/core/security.py                   — PyJWT вместо python-jose
~ backend/app/core/executor.py                   — RestrictedFeatureError + подсказка (RP 8.5)
~ backend/app/api/v1/tasks.py                    — hints требует аутентификации (S20-003)
~ backend/tests/test_executor.py                 — +2 теста (f-строки, format-векторы)
~ backend/tests/test_sandbox_limits.py           — +3 атаки (format_map, string.Formatter, dunder в f-строке)
~ frontend/package.json, pnpm-lock.yaml          — vitest/@vitest/coverage-v8 4.1.12
~ frontend/nginx.conf                            — CSP + 5 security-заголовков, server_tokens off
~ .github/workflows/ci.yml                       — job Security; временные --ignore-vuln
~ docker-compose.prod.yml                        — ALLOWED_ORIGINS из ENV
~ backend/Dockerfile                              — ENTRYPOINT docker-entrypoint.sh
~ .gitignore                                     — backups/
+ backend/docker-entrypoint.sh                    — alembic upgrade head до старта API (S20-006)
+ backend/.dockerignore, frontend/.dockerignore   — контекст сборки без venv/кэшей/node_modules (S20-006)
~ docs/GETTING_STARTED.md, docs/DESIGN_ADMIN_AND_OPS.md — бэкапы/восстановление, PyPI, авто-миграции
~ docs/SPEC.md, docs/CHANGELOG.md, docs/RELEASES.md, docs/KNOWN_ISSUES.md,
  docs/RULES.md, docs/ARCHITECTURE.md, docs/MANUAL_TESTING_GUIDE.md,
  docs/README.md, README.md, docs/USER_GUIDE.md, TODO_V0.2.md — документация v0.2.0
```

---

## 2. Покрытие

| Проверка | Было | Стало |
|----------|------|-------|
| Frontend unit (Vitest) | 80/80 | **80/80** (апгрейд vitest 4.1.12 без регрессий) |
| E2E Playwright | 12 сценариев | **12/12 passed** (auth 4, chat 3, playground 3, tasks 3; ~1.2 мин) |
| Backend pytest | 298 passed + 1 skipped (до S20-003) | **341 passed + 1 skipped** (342 collected, 200.41 с) |
| `test_executor.py` | — | **+2**: f-string работает; 4 частных случая `.format` блокируются с подсказкой |
| `test_sandbox_limits.py` | — | **+3 атаки**: dunder в f-строке, `format_map`, `string.Formatter` |
| `test_access_matrix.py` | — | **35 passed** (17 функций, 43.29 с); IDOR не найден |
| `pnpm audit` | 5 (2 critical + 3 moderate) | **0** |
| `pip-audit -r requirements.txt` | 66 записей в 7 пакетах | **16 записей в 2 пакетах, 0 critical** |
| `gitleaks git .` | — | **0 утечек** на 42 коммитах |
| nginx security headers | нет | **6 заголовков** + `server_tokens off` |
| Backup/restore smoke | нет | **14/14 таблиц**, счётчики совпали |
| Миграции | head 010 | **head 010** (новых нет; `alembic check` — финальный гейт) |

---

## 3. Результаты

Команды — из корня репозитория; backend-аудит — в `python:3.12-slim`, потому
что PyPI с хоста заблокирован (KI-017); CI-job'ы не запускались (KI-014).

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Frontend: аудит | `pnpm --dir frontend audit` | **0** уязвимостей (было 5) |
| Frontend: качество | `pnpm --dir frontend typecheck && lint && test && build` | typecheck/lint 0, **80/80** тестов, build OK, entry **78.71 kB gzip** |
| Frontend: offline | `pnpm --dir frontend test:offline` | CDN в бандле нет |
| Backend: аудит (CI-путь) | `pip-audit -r backend/requirements.txt` в `python:3.12-slim` | **66 → 16 записей в 2 пакетах** (0 critical) |
| Backend: CI-команда с ignores | тот же pip-audit + 8 `--ignore-vuln` (7 starlette + 1 pytest) | **«No known vulnerabilities found, 16 ignored»**, exit 0 |
| E2E | `pnpm e2e` (Playwright chromium, backend `echo`, БД `ai_teacher_e2e`) | **12/12 passed**, ~1.2 мин |
| Backend: JWT/multipart smoke | скрипт без БД: round-trip, expired/forged, Form | OK (5 сценариев) |
| Backend: импорт | `python -c "import app.main"` | OK |
| Локальный аудит | `python scripts/audit_python_deps.py` | таблица + exit 1 на high (до фикса); при исчерпании квоты — exit 2 |
| Ruff (изменённые файлы) | `ruff check app tests scripts` | 0 |
| gitleaks | `gitleaks git . --config .gitleaks.toml --redact` | **0 утечек** / 42 коммита; негативный контроль — 3/3 правила ловят |
| nginx | `nginx -t` (1.27-alpine) | `syntax is ok`, test successful |
| CSP + Monaco | Playwright: AMD-loader под CSP | `MONACO_LOADED: true`, 0 console errors |
| Docker build backend | `docker build ./backend` | успешно: pyjwt 2.15.1, multipart 0.0.31, python-jose отсутствует |
| Prod-compose build + up | `docker compose -p ai_teacher_prod -f docker-compose.prod.yml build && up -d` | 4/4 сервиса **healthy**; образы backend/frontend собраны |
| Prod-migrations | `docker logs ai_teacher_prod-backend-1` | `docker-entrypoint.sh` применил `004→010` до старта uvicorn; чистая БД ожила |
| Prod API smoke | `GET /api/v1/health`, register/login/me, `/tasks`, `/chat/search`, `/code/execute` | health `version 0.2.0`; register 201, login 200, me 200; tasks 200; search anon 403 / auth 200; admin как student 403; execute 200 `2`, `.format` → `RestrictedFeatureError`, dunder → `SecurityError` |
| Prod headers | `curl -I http://127.0.0.1:3080/` | CSP + 5 заголовков + HSTS, `nosniff`, `DENY`; SPA-fallback `/dashboard` → 200 `text/html` |
| Backup | `bash scripts/backup.sh -o <tmp>/backups` | `*.dump.gz` (8.8 kB) + `.sha256`, `pg_restore -l` OK |
| Restore | `restore.sh -t ai_teacher_restore_check --create -y --verify` | **14/14 таблиц**, users 5/5, tasks 6/6, chat 2/2 |
| Guard | `restore.sh -f <dump> -t ai_teacher` без `--force` | exit 2, отказ |
| prod-compose | `docker compose -f docker-compose.prod.yml config` без секретов | падает с `:?` — дефолтных секретов нет |
| YAML | `yaml.safe_load` для `ci.yml` и `dependabot.yml` | OK |
| Backend pytest | `pytest -q` | **341 passed, 1 skipped** (342 collected), 200.41 с |
| Матрица доступа | `pytest tests/test_access_matrix.py -q` | **35 passed**, IDOR не найден |
| Нагрузочный smoke (S19-006, смежный) | `backend/scripts/load_test.py` | health/tasks PASS; submit p95 2219.7 мс ❌ (knee ≈2 RPS) — KI-022 |

Не запускалось: GitHub Actions (KI-014 — биллинг). E2E выполнен финально —
**12/12**. Docker prod build+smoke выполнен Lead'ом на изолированном
compose-проекте `ai_teacher_prod` (порт 3080, свои volume'ы; после проверки
`down -v`, dev-контейнеры не затронуты): найдено и исправлено то, что
prod-стек не применял миграции — добавлен `backend/docker-entrypoint.sh`
(`alembic upgrade head` до uvicorn, `SKIP_MIGRATIONS=true` для отключения),
`.dockerignore` для backend/frontend; повторный smoke на чистой БД — зелёный.

---

## 4. Smoke (ручной сценарий)

1. **Секреты.** Во временный файл положить фейковые `sk-…`,
   `postgresql://user:pass@host/db`, `SECRET_KEY=…` → gitleaks находит все 3
   правила; файл с `change_me_*`/`your_*_here` — не срабатывает (allowlist).
2. **Заголовки.** `nginx:1.27-alpine` с `frontend/nginx.conf`:
   `curl -I /` → CSP, `nosniff`, `DENY`, `Referrer-Policy`,
   `Permissions-Policy`, HSTS; `GET /some/spa/route` → 200 `index.html`;
   `/index.html` → `Cache-Control: no-cache`.
3. **CSP + Monaco.** Playwright: страница `/code` под CSP — Monaco загрузился,
   ошибок в консоли 0, `unsafe-eval` не потребовался.
4. **Бэкап.** `bash scripts/backup.sh` → дамп + sha256, `pg_restore -l` OK;
   retention: бэкап с mtime −40 дней удалён при `-r 14`.
5. **Восстановление.** `restore.sh ... --create -y --verify` → 14/14 таблиц,
   `alembic_version=010`; повторный запуск без `--force` в `ai_teacher` →
   отказ (exit 2); scratch-БД удалена.
6. **Прод-конфиг.** Запуск prod-compose без `POSTGRES_PASSWORD`/`SECRET_KEY` →
   ошибка `:?` (дефолтных секретов нет); `DEBUG=false`; порты БД/Redis наружу
   не публикуются; `ALLOWED_ORIGINS` берётся из ENV.
7. **JWT.** Access/refresh round-trip, просроченный/поддельный токен → `None`
   (401-путь), bcrypt hash/verify, разбор `Form` — OK на PyJWT 2.15.1 и
   python-multipart 0.0.31.
8. **Аудит без PyPI.** `audit_python_deps.py` при исчерпанной квоте GitHub
   API → предупреждение, сохранённый курсор `--resume`, **exit 2** (не
   ложное «чисто»).
9. **Песочница.** `"{x}".format(x=1)` → `error_type=RestrictedFeatureError` +
   подсказка; `print(f"x={5}")` и `print("%d" % 5)` работают; dunder в
   f-строке — `SecurityError`.
10. **Доступ.** `GET /tasks/{id}/hints/0` без токена → 403 (S20-003, F1;
    с невалидным токеном — 401).
11. **Матрица доступа.** `pytest tests/test_access_matrix.py -q` → **35 passed**;
    IDOR не найден; после фикса F1 аноним на hints → 403 (невалидный токен →
    401), student → 200. Полная матрица — [ACCESS_MATRIX.md](ACCESS_MATRIX.md).

---

## 5. Что не так

- **CI не запускался** (KI-014): job `Security` (pip-audit, gitleaks, pnpm
  audit) и `e2e` на GitHub не выполнялись; локальные эквиваленты проверены.
  Нельзя утверждать «CI зелёный» — только «локально зелёные, CI не стартовал».
- **Остаточные уязвимости приняты:** `starlette 0.41.3` (7 ID, high —
  PYSEC-2026-161/248; транзитивно от `fastapi 0.115.5`, векторы не
  используются — KI-015) и dev-only `pytest 8.3.3` (PYSEC-2026-1845 — KI-016).
  Формулировка «аудит полностью чистый» некорректна.
- **PyPI с хоста заблокирован** (KI-017): апгрейды `restrictedpython`/
  `pyjwt`/`python-multipart` ставились через Docker-wheelhouse; локальный venv
  3.11 может отличаться от CI (3.12) — версии сверять с `requirements.txt`.
- **RP 8.5 меняет поведение песочницы:** `.format()`/`format_map`/
  `string.Formatter` запрещены (KI-018) — user-visible ограничение,
  задокументировано в USER_GUIDE и SPEC.
- **Временные `--ignore-vuln` в CI** (8 ID: 7 starlette + 1 pytest): job
  зелёный, но игноры нужно убрать после апгрейдов, иначе они скроют
  исправленные находки.
- **S20-003:** 35 тестов (17 функций), IDOR не найден; одна находка F1 (LOW) —
  hints был анонимным — исправлена в этом же спринте.
- **Нагрузочный тест S19-006** (смежный, влияет на DoD релиза): профиль
  зафиксирован — health 50 RPS p95 6.3 мс, tasks 20 RPS p95 25.4 мс (PASS);
  submit 5 RPS не достигнуты: факт 2.5 RPS, p95 2219.7 мс при бюджете 2000 мс,
  knee ≈2 RPS — ограничение песочницы, **KI-022** (см. LOAD_TEST §5).
- **Финальный гейт:** полный pytest перезапущен Lead'ом после правок
  документации (**341 passed, 1 skipped**); Docker prod build+smoke на
  изолированном compose-проекте — зелёный (нашлась и исправлена дырка:
  prod-стек не применял миграции — теперь `docker-entrypoint.sh` делает
  `alembic upgrade head`); тег `v0.2.0`/GitHub Release — после него;
  CI не стартовал (KI-014).

---

## 6. Новые KI

| KI | Статус | Severity | Суть |
|----|--------|----------|------|
| KI-015 | Accepted | High | `starlette 0.41.3` (транзитивно от fastapi): 7 ID, апгрейд отложен до v0.3.0 |
| KI-016 | Accepted | Low | dev-only `pytest 8.3.3` advisory (PYSEC-2026-1845) |
| KI-017 | Open | Low | PyPI недоступен с хоста; аудит — Docker/GitHub Advisory API |
| KI-018 | Accepted | Low | `.format()` заблокирован в песочнице после RP 8.5 |
| KI-019 | Resolved | Critical | python-jose/PyJWT/python-multipart — закрыто (PyJWT 2.15.1, 0.0.31) |
| KI-020 | Resolved | Critical | frontend vitest/tinypool criticals — закрыто (4.1.12) |
| KI-021 | Resolved | High | RestrictedPython 7.4 (3 обхода) — закрыто (8.5) |
| KI-022 | Accepted | Med | Предел throughput `submit` ≈2 RPS (песочница); 5 RPS не достигнуты, рекомендации в LOAD_TEST §5 |

KI-014 остаётся Open (биллинг GitHub Actions): обновлена дата, статус не
менялся — доказательств восстановления CI нет.

---

## 7. Обоснование

- **PyJWT вместо python-jose.** `python-jose` использовался в одном модуле
  (`app/core/security.py`), API `encode/decode` совместим; удаление убирает
  2 critical + транзитивные `ecdsa`/`rsa`. Полный pytest в момент фикса был
  недоступен (одна тестовая БД у S19), поэтому — доказательный smoke:
  пин-версии проверены на PyPI в контейнере, `pip check`, JWT/multipart
  сценарии, `docker build`.
- **Апгрейд vitest 4.1.12.** Все находки — dev-зависимости тестового
  toolchain; мажорный апгрейд не потребовал правок конфигов, тесты/сборка
  зелёные, аудит чистый.
- **RestrictedPython 8.5.** Три high-обхода песочницы важнее удобства
  `.format()`: закрыты `try/except*`, shadowing guard-хуков и
  `string.Formatter`; вместо сырого `NotImplementedError` — понятная ошибка
  `RestrictedFeatureError` и тесты на f-строки/%. Альтернатива (остаться на
  7.4) оставляла обходы sandbox.
- **CSP без `unsafe-eval`.** Monaco локальный (S19-001), AMD-loader и worker'ы
  идут с собственного origin; `style-src 'unsafe-inline'` нужен React/
  Tailwind/Monaco. Проверено Playwright, а не «на глаз».
- **Заголовки на уровне `server`.** `add_header` в `location` отменяет
  наследование; поэтому кэш `/assets/` — через `expires`, а заголовки — на
  `server` с `always`.
- **pip-audit в Docker как авторитетный источник.** Хост не видит PyPI, а CI —
  ровно тот же путь (`pip-audit -r requirements.txt`); локальный скрипт по
  GitHub Advisory API — только fallback с честным exit 2 при неполных данных.
- **Бэкапы через `docker exec pg_dump`.** Не требует локального `pg_dump` и
  гарантирует «свою» БД (KI-001); restore по умолчанию в scratch-БД +
  guard — чтобы проверка не могла затереть рабочую базу.
- **Временные `--ignore-vuln`.** Без них job был бы красным на известных
  принятых рисках и перестал бы ловить новые; список ID синхронизирован с
  KI-015/016 и отчётом аудита, после апгрейдов удаляется.
- **Матрица доступа — отдельные отчёт+тест.** Аудит прав должен быть
  воспроизводимым артефактом, а не разовой ручной проверкой: параметризованный
  тест фиксирует 401/403/404 для чужих ресурсов (S20-003).
