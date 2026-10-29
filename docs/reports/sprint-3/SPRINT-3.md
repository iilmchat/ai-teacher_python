# Sprint 3: Authentication — Отчёт

**Период:** 2026-10-29
**Статус:** ✅ Завершён

---

## 1. Файлы (+/-)

### Созданные
```
+ backend/app/core/security.py          — bcrypt, JWT, get_current_user, require_role
+ backend/app/core/rate_limiter.py      — middleware rate limiting на Redis
+ backend/app/api/v1/auth.py            — 6 эндпоинтов аутентификации
+ backend/tests/test_auth.py            — 14 тестов
```

### Изменённые
```
~ backend/app/main.py                   — подключён auth-роутер, structlog вместо print
~ backend/app/config.py                 — .env по абсолютному пути, порты 5434/6381
~ backend/app/models/__init__.py        — явные импорты моделей (иначе metadata пустая)
~ backend/app/models/user.py            — values_callable, индексы как в миграции
~ backend/app/models/chat.py            — values_callable, metadata → session_metadata
~ backend/app/schemas/user.py           — password max_length=72, типы settings
~ backend/app/db/repositories/base.py   — типизация, list() вместо Sequence
~ backend/app/db/repositories/chat.py   — типизация code_blocks
~ backend/tests/conftest.py             — PostgreSQL + транзакционный откат
~ backend/tests/test_health.py          — асинхронные тесты
~ backend/alembic/env.py                — URL из Settings
~ backend/alembic/versions/20261029_0001_initial.py — pgvector, JSONB defaults
~ backend/requirements.txt              — bcrypt вместо passlib, psycopg2-binary
~ docker-compose.yml                    — pgvector-образ, параметризованные порты
~ .env / .env.example                   — порты 5434/6381
~ pyproject.toml                        — B008 в ignore, mypy overrides, pytest loop scope
~ .github/workflows/ci.yml              — pgvector-сервис, alembic check, порты
```

---

## 2. Покрытие

| Файл | Тестов |
|------|--------|
| `tests/test_auth.py` | 14 |
| `tests/test_health.py` | 3 |
| **Итого** | **17** |

Проверяемые сценарии: регистрация, дубли email/username, невалидный email,
короткий пароль, вход по username и по email, неверный пароль, неизвестный
пользователь, `GET /me`, обновление токена, отказ при access-token в refresh,
доступ без токена, `PATCH /me`.

---

## 3. Результаты

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Линтер | `ruff check app tests` | `All checks passed!` |
| Типы | `mypy app --config-file ../pyproject.toml` | `Success: no issues found in 23 source files` |
| Тесты | `pytest -q` | `17 passed in 10.05s` |
| Миграции | `alembic upgrade head` | `Running upgrade -> 001, initial tables` |
| Схема | `alembic check` | расхождений нет |
| Containers | `docker compose ps` | postgres `127.0.0.1:5434->5432`, redis `127.0.0.1:6381->6379`, оба healthy |

---

## 4. Smoke

Ручной сценарий на запущенном сервере (`uvicorn app.main:app --port 8000`):

```
POST /api/v1/auth/register → 201
POST /api/v1/auth/login    → 200 (access_token + refresh_token)
GET  /api/v1/auth/me       → 200
{
  "email": "smoke2@example.com",
  "username": "smokeuser2",
  "role": "student",
  "level": "basic",
  "settings": {}
}
GET /api/v1/health → {"status":"ok","version":"0.1.0",...}
```

---

## 5. Что не так

1. **Rate limiting не подключён к приложению.** Модуль готов
   (`create_rate_limit_middleware`), но `main.py` его не регистрирует — нужен
   lifecycle-хук для Redis-клиента. Перенесено в спринт 4.
2. **Logout не инвалидирует токены.** JWT stateless: клиент удаляет токены сам;
   серверный denylist в Redis появится вместе с rate limiting.
3. **KI-001 (порты 5434/6381)** — обходной путь, не закрыто.
4. **KI-002** — нет теста, сверяющего модели с миграциями (только `alembic check`
   в CI).
5. Python на машине 3.11.8 вместо 3.12 (CI гоняет 3.12).

---

## 6. Новые KI

| ID | Статус | Severity | Суть |
|----|--------|----------|------|
| KI-001 | Open | Med | Порты 5432/6379 заняты чужими контейнерами |
| KI-002 | Open | Low | Нет автотеста на расхождение моделей и миграций |
| KI-003 | Resolved | High | Образ без pgvector |
| KI-004 | Resolved | High | Enum хранил имена вместо значений |
| KI-005 | Resolved | High | passlib несовместим с bcrypt 5.x |

---

## 7. Обоснование

- **bcrypt напрямую вместо passlib.** passlib 1.7.4 несовместим с bcrypt 5.x
  (KI-005). Прямой bcrypt — одна зависимость вместо двух и предсказуемое
  поведение.
- **`values_callable` для enum.** Значения в БД (`student`) читаемее имён
  (`STUDENT`) и совпадают с API-контрактом (KI-004).
- **Разделение токенов по типу.** `type` в payload исключает использование
  access-токена как refresh (покрыто тестом).
- **Тесты на реальном PostgreSQL.** SQLite не умеет JSONB и VECTOR; тестовая БД
  в транзакции с откатом даёт изоляцию без потери производительности.
- **Вход по username или email.** Снижает число обращений в поддержку,
  реализуется без изменения схемы БД.
- **`_user_id_from_payload` вынесен в функцию.** Убирает дублирование логики
  разбора `sub` между refresh и `get_current_user`.

---

**Дата:** 2026-10-29
