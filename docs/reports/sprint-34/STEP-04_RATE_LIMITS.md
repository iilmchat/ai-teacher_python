# S34-004 — лимиты refresh и per-user песочницы

**Дата:** 2026-11-11
**Спринт:** 34 (P0: Auth & Edge Hardening)
**Статус:** завершено

## Проблема

`/auth/refresh` попадал под общий лимит 300/мин на IP — слишком мягко для
эндпоинта, который делает bcrypt и работу с БД. `/code/execute` ограничивался
только общим IP-лимитом, поэтому один пользователь мог выжигать песочницу.

## Изменения

- `backend/app/core/rate_limiter.py`:
  - `REFRESH_PATH = "/api/v1/auth/refresh"`, `REFRESH_LIMIT = 30`;
  - `CODE_EXECUTE_LIMIT = 30`;
  - middleware выделяет refresh в отдельный ключ `refresh:<ip>`.
- `backend/app/api/v1/code.py` — в `POST /code/execute` проверка
  `is_user_limited("code_execute", user_id, CODE_EXECUTE_LIMIT)`;
  при превышении `429` + `Retry-After: 60`.
- `backend/tests/test_rate_limit.py` — 6 новых тестов:
  - refresh блокируется после `REFRESH_LIMIT`;
  - исчерпание login-лимита не блокирует refresh;
  - per-user блокировка после лимита;
  - изоляция пользователей;
  - отключение флагом `RATE_LIMIT_ENABLED=false`;
  - fail-open при недоступном Redis.

## Проверки

```
cd backend && python -m pytest tests/test_rate_limit.py tests/test_code_api.py -q
# 34 passed
```

## Поведение

| Эндпоинт | Лимит | Ключ |
|----------|-------|------|
| `POST /auth/login` | 5/мин | IP (с учётом `TRUSTED_PROXIES`) |
| `POST /auth/refresh` | 30/мин | IP |
| остальные | 300/мин | IP |
| `POST /code/execute` | 30/мин | user_id |
| `POST /tasks/{id}/check` | 20/мин | user_id |

Все лимиты fail-open: при недоступном Redis запросы проходят с warning.
