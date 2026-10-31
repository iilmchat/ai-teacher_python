# Шаг 01/спринт 22: контрактные тесты API

**Дата:** 2026-10-31  
**Спринт:** 22 (v0.3.0)  
**Задача:** S22-001  
**Статус:** ✅ выполнено

---

## 1. Что сделано

1. **Снапшот OpenAPI** — `backend/tests/contracts/openapi.json` (68 операций,
   92 схемы, 171 КБ) и генератор `backend/scripts/snapshot_openapi.py`
   (`--check` — проверка без записи).
2. **Компаратор контрактов** — `backend/tests/contract_utils.py`:
   - `diff_openapi(expected, actual)` — breaking-изменения: удалённый путь/
     операция/код ответа/тип media-type, удалённое поле или схема, смена типа,
     удалённое значение `enum`, **новое обязательное** поле;
     аддитивные изменения (новые пути, поля, значения enum, коды) разрешены;
   - `diff_shape(expected, actual)` — те же правила для «формы» JSON-ответа;
   - резолв локальных `$ref` с защитой от циклов.
3. **Тест снапшота** — `backend/tests/test_contract_openapi.py` (12 тестов:
   сам снапшот + юнит-тесты каждого правила на миниатюрных спеках).
4. **Формы ответов ключевых эндпоинтов** — `backend/tests/test_api_contract_shapes.py`
   + `tests/contracts/endpoints.json` (21 форма: auth register/login/me, tasks
   list/detail/submit/progress/404, chat session/message/list/detail/search,
   classrooms create/join/assignment/detail/progress, me/assignments,
   admin analytics). Значения не сравниваются — только структура; новые поля
   разрешены, пропавшие — нет.
5. **Перегенерация фикстур** — осознанно, переменной окружения:
   `UPDATE_CONTRACT_FIXTURES=1 pytest -q tests/test_api_contract_shapes.py`.
6. **Фейковый LLM вынесен** в `backend/tests/fake_llm.py` (был локальным
   классом в `test_chat.py`) — контрактные тесты используют тот же фейк.

---

## 2. Проверки

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Ruff | `ruff check app tests scripts` | 0 |
| MyPy strict | `mypy app --config-file ../pyproject.toml` | 0 |
| Контрактные тесты | `pytest -q tests/test_contract_openapi.py tests/test_api_contract_shapes.py` | **13 passed** |
| Повторный прогон (стабильность) | то же, без `UPDATE_CONTRACT_FIXTURES` | 13 passed, фикстура не меняется |

---

## 3. Файлы

```
+ backend/scripts/snapshot_openapi.py
+ backend/tests/contract_utils.py
+ backend/tests/test_contract_openapi.py
+ backend/tests/test_api_contract_shapes.py
+ backend/tests/contracts/openapi.json
+ backend/tests/contracts/endpoints.json
+ backend/tests/fake_llm.py
~ backend/tests/test_chat.py        — использует общий фейк
```

---

## 4. Проблемы и отклонения

1. **Первый прогон упал на импорте `sys`** в `check_version.py` (ruff F821) —
   поймано локальным ruff в контейнере; исправлено.
2. **Тесты инструментов релиза не находили `docs/RELEASES.md` и
   `frontend/package.json`** в CI-копии: `backend-test.sh` копировал только
   `backend` и `pyproject.toml`. Исправлено в S21-доработке (копируются оба
   файла), здесь подтверждено полным прогоном.
3. **Форма пустого списка `[]`** неинформативна — фикстура фиксирует элемент
   только если он есть; для пустых выдач проверяется лишь то, что пришёл
   список. Это осознанное ограничение (иначе тест зависел бы от данных).

---

## 5. Обоснование

- **Снапшот, а не «проверка отдельных полей».** Апгрейд `fastapi`/`starlette`
  (S22-002) меняет генерацию OpenAPI; без снапшота это заметили бы клиенты.
- **Аддитивность как правило, а не как «сравнение строк».** Полный diff
  JSON-файла ломался бы на любом новом поле и требовал перегенерации на каждый
  чих; компаратор разрешает безопасные изменения и падает только на breaking.
- **Формы ответов, а не значения.** Значения зависят от данных и времени
  (`created_at`, `score`), форма — от контракта. Фикстура не «протухает».
- **Перегенерация через env-переменную.** Отдельный скрипт-снапшот ответов
  потребовал бы БД и авторизации вне pytest; тест уже имеет и то, и другое.
