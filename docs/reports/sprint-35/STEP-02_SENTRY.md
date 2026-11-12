# S35-002 — Sentry (backend + frontend) без PII

**Дата:** 2026-11-12
**Спринт:** 35 (Observability & Monitoring)
**Статус:** завершено

## Backend

- `backend/requirements.txt`: `sentry-sdk[fastapi]==2.74.0`.
- `backend/app/config.py`: `SENTRY_DSN`, `SENTRY_ENVIRONMENT`,
  `SENTRY_TRACES_SAMPLE_RATE`, `SENTRY_RELEASE`.
- `backend/app/core/sentry.py`:
  - `init_sentry()` — no-op без DSN; ошибка инициализации логируется и не
    роняет старт;
  - `send_default_pii=False`, `max_request_body_size="never"`;
  - `before_send` вычищает: `request.data/cookies/query_string`, секретные
    заголовки (`Authorization`, `Cookie`, `X-Forwarded-For`), `user.email/
    username/ip_address` (остаётся только `id`), `extra`-ключи с кодом,
    промптами, токенами, паролями; строки кода в stacktrace; маскирует email
    и IPv4/IPv6 в сообщениях (`<email>`, `<ip>`).
- `backend/app/main.py`: `init_sentry()` после `configure_logging()`.

## Frontend

- `@sentry/react@11.12.0`.
- `frontend/src/lib/sentry.ts`: `initSentry()` и `scrubSentryEvent()`.
- Runtime-конфиг: `frontend/public/config.js` + `index.html` (script до
  приложения); `frontend/docker-entrypoint.d/40-runtime-config.sh` пишет
  `/config.js` из ENV (`SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `APP_RELEASE`,
  `SENTRY_TRACES_SAMPLE_RATE`) — один образ, разные окружения.
- PII: `dataCollection` отключает userInfo/cookies/headers/bodies/query;
  `beforeSend` повторяет серверную чистку.
- `frontend/nginx.conf`: CSP `connect-src` разрешает `*.sentry.io` /
  `*.ingest.sentry.io`; `/config.js` не кэшируется.
- `frontend/src/main.tsx`: `initSentry()` до рендера.

## Конфигурация

`.env.example` и `docker-compose.prod.yml`:

```env
SENTRY_DSN=
SENTRY_ENVIRONMENT=development
SENTRY_TRACES_SAMPLE_RATE=0
SENTRY_RELEASE=
```

## Проверки

```
cd backend && pytest tests/test_sentry.py -q                    # 6 passed
cd frontend && pnpm exec vitest run src/test/sentry.test.ts     # 5 passed
cd frontend && pnpm run typecheck && pnpm exec eslint src/lib/sentry.ts
```

Тесты проверяют: no-op без DSN, удаление тела/куки/query, отсутствие email/IP
пользователя, фильтрацию кода/промптов, маскирование email/IP, отсутствие
исключений в фильтре.
