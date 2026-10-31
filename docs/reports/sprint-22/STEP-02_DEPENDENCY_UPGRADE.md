# Шаг 02/спринт 22: апгрейд зависимостей (KI-015, KI-016)

**Дата:** 2026-10-31  
**Спринт:** 22 (v0.3.0)  
**Задачи:** S22-002, S22-003  
**Статус:** ✅ выполнено; поведенческое изменение (401) зафиксировано в SPEC и тестах

---

## 1. Что сделано

1. **`fastapi 0.115.5 → 0.162.0`, `starlette 0.41.3 → 1.10.0`** (KI-015).
   Новые транзитивные зависимости: `annotated-doc 0.0.5`,
   `opentelemetry-api 1.45.2`; `pydantic 2.10.1` осталась совместимой.
   `starlette` закреплён в `requirements.txt` явно — он больше не «случайный»
   транзитивный пакет с уязвимостями.
2. **`pytest 8.3.3 → 9.2.0`, `pytest-asyncio 0.24.0 → 1.4.1`,
   `pytest-cov 6.0.0 → 7.1.0`, `pytest-env 1.1.5 → 1.8.3`** (KI-016).
   Конфиг `pyproject.toml` не потребовал правок: `asyncio_mode`,
   `asyncio_default_fixture_loop_scope`, `testpaths`, маркеры — без
   предупреждений об устаревших опциях.
3. **Поведенческое изменение: 401 вместо 403.** Без заголовка `Authorization`
   Starlette 1.x отвечает `401` + `WWW-Authenticate` (RFC 7235), раньше
   FastAPI `HTTPBearer` отдавал `403`. Обновлены `test_access_matrix`,
   SPEC §7 (три места) и CHANGELOG; фронтенд уже обрабатывает 401
   (refresh → логин), правок не потребовалось.
4. **Снапшот OpenAPI перегенерирован** (осознанно, отдельным изменением):
   `format: password` у OAuth2-полей, `pattern: ^password$`,
   `contentMediaType` вместо `format: binary` у загружаемого файла,
   `ValidationError.ctx/input` (аддитивно). Удалённых полей/путей/кодов нет.
5. **`pip-audit` в CI — без `--ignore-vuln`.** 7 starlette-advisory и
   dev-pytest закрыты; проверка: «No known vulnerabilities found» (без игноров).
6. **KNOWN_ISSUES:** KI-015 и KI-016 → `Resolved`; CHANGELOG `[Unreleased]`;
   ARCHITECTURE (версии, аудит зависимостей); RULES §11.21.

---

## 2. Проверки

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Контракт API | `pytest -q tests/test_contract_openapi.py tests/test_api_contract_shapes.py` | **13 passed** (breaking нет) |
| Полный backend | `pytest -q` | **367 passed, 1 skipped** (113 с) |
| Ruff / MyPy | `ruff check app tests scripts` / `mypy app` | 0 / 0 |
| Зависимости | `pip check` | OK |
| Аудит | `pip-audit -r requirements.txt --strict --desc` (контейнер, OSV) | **0 находок** |
| Миграции | `alembic upgrade head` + `check` (в job `test`) | OK (CI) |
| e2e | Playwright 12/12 (CI, job `E2E`) | см. SPRINT-22 |

---

## 3. Файлы

```
~ backend/requirements.txt                 — пины fastapi/starlette/pytest-*
~ backend/tests/contracts/openapi.json     — перегенерирован
~ backend/tests/test_access_matrix.py      — 401 вместо 403
~ .github/workflows/ci.yml                 — pip-audit без игноров
~ gitflic-ci.yaml                          — pip-audit без игноров
~ scripts/ci/security-backend.sh           — pip-audit без игноров
~ docs/SPEC.md                             — §7: конвенция 401
~ docs/ARCHITECTURE.md                     — версии зависимостей
~ docs/CHANGELOG.md, docs/KNOWN_ISSUES.md  — записи S22-002/003
~ docs/RULES.md                            — §11.21
```

---

## 4. Проблемы и отклонения

1. **Один тест упал на апгрейде** — `test_missing_credentials_403_and_invalid_token_401`
   (401 вместо 403). Это не регрессия, а изменение стандартного поведения
   Starlette; тест и SPEC обновлены, поведение описано в CHANGELOG.
2. **`filterwarnings = error` не включён.** В прогоне ~1 400 предупреждений
   `datetime.utcnow()` (deprecated с Python 3.12) — при `error` CI стал бы
   красным на ровном месте. Это отдельная чистка (кандидат в спринт 25/30);
   решение зафиксировано в RULES §11.21 п. 8 и в отчёте.
3. **PyPI с машины недоступен** — апгрейд ставился из зеркала `mirrors.aliyun.com`,
   wheelhouse пересобран под новые пины (см. STEP-03).

---

## 5. Обоснование

- **Почему `starlette` теперь в пинах.** Иначе версия снова «приедет» транзитивно
  и следующий advisory будет не виден в diff'е требований.
- **Почему 401 принят, а не «сохранён 403».** Обратная совместимость важна для
  успешных ответов и полей; код ошибки аутентификации — стандартизован
  (RFC 7235), а единственный клиент (`frontend/src/lib/api.ts`) уже ветвится
  по 401. Возвращать 403 означало бы патчить Starlette ради неверного кода.
- **Почему снапшот обновлён в том же PR.** Это часть апгрейда: отдельный PR
  «перегенерировать снапшот» сломал бы контрактный тест на промежуточном commit.
  В коммите указано, какие изменения аддитивные.
- **Почему pytest 9 сразу, а не отдельным спринтом.** Dev-зависимость,
  risk-free (полный прогон зелёный), а игнор `PYSEC-2026-1845` в CI хотелось
  убрать вместе со starlette-игнорами — иначе аудит остаётся «с оговоркой».
