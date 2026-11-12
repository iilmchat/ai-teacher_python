# S38-003 — Caddy: security headers, CSP, HSTS

**Дата:** 2026-11-12
**Спринт:** 38
**Статус:** завершено

## Caddyfile

Добавлены заголовки на edge:

- `Content-Security-Policy`: `script-src 'self'`, `style-src 'self'
  'unsafe-inline'` (Monaco/Tailwind), `worker-src 'self' blob:` (Monaco),
  `connect-src 'self' https://*.sentry.io https://*.ingest.sentry.io`,
  `frame-ancestors 'none'`, `object-src 'none'`;
- `X-Frame-Options: DENY`;
- `X-Content-Type-Options: nosniff`;
- `Referrer-Policy: strict-origin-when-cross-origin`;
- `Permissions-Policy` (без камеры/микрофона/геолокации);
- `Cross-Origin-Opener-Policy: same-origin`,
  `Cross-Origin-Resource-Policy: same-origin`;
- `Strict-Transport-Security` — только в TLS site-блоке; HTTP-редирект Caddy
  обслуживает отдельным сервером без HSTS. HSTS убран из nginx (prod edge —
  Caddy).

## Swagger

`DOCS_ENABLED=false` в prod-compose (S34-006) — `/api/docs`, `/api/redoc`,
`/api/openapi.json` возвращают 404. Caddy проксирует `/api/*`, но маршрутов
документации в backend нет.

## Проверки

```
docker run ... caddy validate ...        # Valid configuration
pytest tests/test_deploy_config.py       # заголовки + DOCS_ENABLED=false
cd frontend && pnpm build && pnpm test:offline
# build OK; no CDN references
```

CSP проверен статически: `script-src 'self'` не блокирует Vite-бандлы,
Monaco использует разрешённые `blob:` worker и inline-стили, Sentry —
разрешённый ingest. Полный браузерный e2e с Caddy не запускался (нет TLS-
домена); конфигурация валидирована.
