# S34-006 — флаг DOCS_ENABLED

**Дата:** 2026-11-11
**Спринт:** 34 (P0: Auth & Edge Hardening)
**Статус:** завершено

## Проблема

Swagger UI, ReDoc и OpenAPI-схема были доступны всегда, в том числе в
production. Это раскрывает структуру API и облегчает разведку.

## Изменения

- `backend/app/config.py` — `docs_enabled: bool = True`.
- `backend/app/main.py`:
  - `docs_urls(enabled)` возвращает `DocsConfig` (TypedDict);
  - при `DOCS_ENABLED=false` в `FastAPI` передаются `docs_url=None`,
    `redoc_url=None`, `openapi_url=None` — маршруты не регистрируются.
- `.env.example` — `DOCS_ENABLED=true` с комментарием «в production — false».
- `docker-compose.prod.yml` — `DOCS_ENABLED: "false"`, `TRUSTED_PROXIES` по
  умолчанию `127.0.0.1`.
- `backend/tests/test_security_settings.py` — 4 теста: значения helper'а и
  реальные ответы (404 при выключении, 200 при включении).

## Проверки

```
cd backend && python -m pytest tests/test_security_settings.py -q   # 8 passed
```

## Важно

`/metrics` и `/health/*` остаются доступными, как и раньше; их закрытие —
задача reverse-proxy (см. `SECURITY.md`). При `DOCS_ENABLED=false` контрактный
снапшот по-прежнему строится из `app.openapi()` в тестах — флаг влияет только
на рантайм-маршруты.
