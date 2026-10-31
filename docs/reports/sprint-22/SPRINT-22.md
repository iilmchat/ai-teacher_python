# SPRINT-22.md — Dependency Modernization (v0.3.0)

**Период:** 2026-10-31  
**Задачи:** S22-001…S22-006  
**Статус:** ✅ завершён: `fastapi`/`starlette`/`pytest` обновлены, контракт API
зафиксирован тестами, `pip-audit` без игноров; ⚠️ авто-мерж Dependabot
невозможен на GitHub Free/private (`KI-023`)

---

## 1. Файлы (+/-)

```
+ backend/scripts/snapshot_openapi.py            — генератор снапшота OpenAPI
+ backend/tests/contracts/openapi.json           — снапшот (68 операций, 92 схемы)
+ backend/tests/contracts/endpoints.json         — 21 форма ответов
+ backend/tests/contract_utils.py                — компаратор (аддитивность)
+ backend/tests/test_contract_openapi.py         — 12 тестов
+ backend/tests/test_api_contract_shapes.py      — формы ключевых эндпоинтов
+ backend/tests/fake_llm.py                      — общий фейковый LLM
+ scripts/wheelhouse.py                          — build/install/list (offline)
+ docs/reports/sprint-22/STEP-01_API_CONTRACT_TESTS.md
+ docs/reports/sprint-22/STEP-02_DEPENDENCY_UPGRADE.md
+ docs/reports/sprint-22/STEP-03_WHEELHOUSE_DEPENDABOT_DOCS.md
+ docs/reports/sprint-22/SPRINT-22.md            — этот отчёт
~ backend/requirements.txt                       — fastapi 0.162, starlette 1.10,
                                                   pytest 9.2 + плагины
~ backend/tests/test_access_matrix.py            — 401 вместо 403
~ backend/tests/test_chat.py                     — использует tests/fake_llm.py
~ backend/tests/contracts/openapi.json           — перегенерирован (аддитивно)
~ .github/workflows/ci.yml                       — pip-audit без игноров
~ gitflic-ci.yaml                                — pip-audit без игноров
~ scripts/ci/security-backend.sh                  — pip-audit без игноров
~ scripts/ci/build-wheelhouse.ps1                 — обёртка над wheelhouse.py
~ .github/dependabot.yml                          — политика S22-004
~ .gitignore                                      — .wheelhouse/
~ docs/SPEC.md                                    — §7: конвенция 401
~ docs/ARCHITECTURE.md                            — версии, аудит
~ docs/CHANGELOG.md, docs/KNOWN_ISSUES.md         — записи спринта 22
~ docs/RELEASES.md, docs/RULES.md                 — журнал, §11.21
~ docs/CI.md, docs/GETTING_STARTED.md             — §13, wheelhouse
~ TODO_V0.3.md                                    — статусы S22-001…006
```

---

## 2. Покрытие

- **`tests/test_contract_openapi.py` — 12 тестов:** снапшот совпадает;
  юнит-тесты каждого правила (удалённый путь/операция/код ответа/поле/схема,
  смена типа, новое обязательное поле, удалённое значение enum, аддитивные
  изменения разрешены).
- **`tests/test_api_contract_shapes.py` — 1 сквозной сценарий, 21 форма:**
  auth (register/login/me), tasks (list/detail/submit/progress/404), chat
  (session create/message/list/detail/search), classrooms (create/join/
  assignment/detail/progress, `/me/assignments`), admin analytics.
- **Регрессия поведения:** `test_access_matrix` фиксирует 401 без заголовка
  и 401 с невалидным токеном; e2e — вход/защищённые маршруты.
- **Непокрытое:** `scripts/wheelhouse.py` — инфраструктурный CLI (как
  `backup.sh`): проверяется запуском (`build`/`list`/`install` + офлайн-lint),
  юнит-тестов нет; `dependabot.yml` — декларативный конфиг.

---

## 3. Результаты

| Проверка | Результат |
|----------|-----------|
| `ruff check app tests scripts` | **0** |
| `mypy app` (strict) | **0** |
| `pytest -q` | **367 passed, 1 skipped** (113 с) |
| Контрактные тесты | 13 passed (breaking-изменений 0) |
| Frontend: typecheck/lint/test/build | 80/80, build 78.71 kB gzip |
| E2E Playwright | **12/12** |
| `pip-audit` (без игноров) | **0 находок** («No known vulnerabilities found») |
| `pnpm audit --audit-level=high` | 0 |
| `alembic upgrade head` + `check` | OK (миграции до `010`) |
| CI `CI (self-hosted fallback)` | **6/6 success**, run
[41216819988](https://github.com/iilmchat/ai-teacher_python/actions/runs/41216819988) |

Build: 0 ошибок / 0 предупреждений. Tests: 367/368 (1 skip — Windows-only).

---

## 4. Smoke

1. `pytest -q tests/test_contract_openapi.py` — снапшот совпадает с живой
   схемой; изменение поля вручную → тест падает с понятным сообщением.
2. Апгрейд в venv (`fastapi==0.162.0`, `starlette==1.10.0`): контрактные тесты
   прошли **до** перегенерации снапшота (breaking нет), diff — 11+/2−
   (косметика OpenAPI).
3. `pytest -q` — 367 passed; единственное падение по ходу — `test_access_matrix`
   (401 вместо 403), исправлено вместе с SPEC.
4. `pip-audit -r backend/requirements.txt --strict --desc` в контейнере
   (`python:3.12-slim`, зеркало + OSV) — «No known vulnerabilities found».
5. `pwsh scripts/ci/build-wheelhouse.ps1 -ListOnly` → 101 колесо, 75 МБ;
   `docker run … backend-lint.sh` с `wheelhouse:ro` → «wheelhouse OK», ruff/mypy 0.
6. CI на PR #28 (run
   [41216819988](https://github.com/iilmchat/ai-teacher_python/actions/runs/41216819988)):
   Frontend → Lint → Security → Test (367 passed) → E2E (12/12) → Docker build —
   **6/6 зелёные**.

---

## 5. Что не так

1. **`filterwarnings = error` не включён** (S22-003, частично): в прогоне
   ~1 400 `DeprecationWarning` на `datetime.utcnow()` в приложении. Включать
   строгий режим до чистки — значит получить красный CI на неизменном коде.
   Решение и порядок записаны в RULES §11.21 п. 8; чистка — кандидат в S25/S30.
2. **Поведенческое изменение 401 vs 403** (S22-002): для внешних клиентов это
   breaking по коду ошибки, но не по смыслу; наш фронтенд уже обрабатывает 401,
   SPEC/CHANGELOG обновлены. Вернуть 403 — значит патчить Starlette ради
   неверного поведения.
3. **Авто-мерж Dependabot недоступен** (S22-004): GitHub Free/private не даёт
   branch protection/auto-merge (`KI-023`). Политика minor/patch (группой после
   зелёного CI) описана, мерж — вручную.
4. **Wheelhouse-том не всегда очищается** `docker volume rm` (занят
   контейнером) — в томе остаются колёса старых версий. На установку не влияет
   (pip выбирает по пину), но объём растёт; лечится `-Recreate` после остановки
   job'ов.
5. **13 открытых PR Dependabot**, включая мажорные `actions/checkout@7`,
   `setup-python@7`, `setup-node@7` — требуют ручной проверки self-hosted job'ов.
6. **PyPI с машины недоступен**: апгрейд и wheelhouse ставились через
   `mirrors.aliyun.com`; это часть `KI-017` (закрыт как процесс, не как сеть).

---

## 6. Новые KI

- **Новых KI нет.** Закрыты `KI-015`, `KI-016`, `KI-017`.
- **`KI-023`** (merge-gate) дополнена: то же ограничение блокирует авто-мерж
  Dependabot minor/patch.

---

## 7. Обоснование

1. **Контрактные тесты — до апгрейда, а не после.** Без снапшота единственным
   признаком breaking-изменения был бы упавший клиент. Компаратор разрешает
   аддитивные изменения, иначе тест пришлось бы перегенерировать на каждое
   новое поле и он перестал бы что-либо ловить.
2. **Один PR на апгрейд, снапшот — в том же коммите.** Отдельный PR
   «перегенерировать снапшот» сломал бы контрактный тест на промежуточном
   коммите и потребовал бы двух ревью одного решения.
3. **`filterwarnings = error` отложен, а не «включён наполовину».** Строгий
   режим с whitelist'ом предупреждений — это скрытая настройка, которую никто
   не поддерживает; лучше явная отсрочка с записанным планом.
4. **Wheelhouse — один скрипт на dev и CI.** Логика скачивания должна быть
   одинаковой; различие (каталог vs named volume) — только в обвязке.
   `--docker` по умолчанию в документации снимает главную ловушку
   «Windows-колёса в Linux-контейнере».
5. **401 принят.** Код ошибки аутентификации — часть стандарта (RFC 7235);
   сохранение 403 потребовало бы обходного слоя и разошлось бы с поведением
   Starlette/FastAPI, которое будет меняться и дальше.
