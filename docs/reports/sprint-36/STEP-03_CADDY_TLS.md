# S36-003 — Caddy, TLS и периметр

**Дата:** 2026-11-12
**Спринт:** 36
**Статус:** завершено

## Конфигурация

`deploy/caddy/Caddyfile`:

- `{$DOMAIN}` — автоматический TLS (Let's Encrypt ACME), HTTP→HTTPS redirect;
- `/api/*` → `backend:8000` (WebSocket upgrade Caddy делает автоматически,
  включая `/api/v1/chat/ws/...`);
- остальное → `frontend:80` (SPA);
- HSTS, `-Server`;
- JSON-логи Caddy;
- health/метрики наружу не проксируются (остаются во внутренней сети).

## Compose

- `caddy` — единственный сервис с `ports`: `${CADDY_HTTP_PORT:-80}:80`,
  `${CADDY_HTTPS_PORT:-443}:443` (пилот: 8080/8443);
- у `frontend` удалён `ports`, только `expose: 80` + `networks: [edge]`;
- `backend` — `expose: 8000`, сети `edge` + `internal`;
- `postgres`/`redis` — только `internal` (network `internal: true`);
- `TRUSTED_PROXIES=10.77.0.0/16` совпадает с подсетью edge — Caddy передаёт
  `X-Forwarded-For`, backend доверяет только этой сети (S34-003);
- `caddy_data`/`caddy_config` — persistent volumes для сертификатов.

## Проверки

```
docker run --rm -e DOMAIN=example.com -v "$PWD/deploy/caddy:/etc/caddy:ro" \
  caddy:2.10.0-alpine caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
# Valid configuration

docker compose --env-file .env.prod.example -f docker-compose.prod.yml config --quiet
# OK
```

## Ограничение

Реальный ACME-выпуск не проверялся (нет публичного домена/DNS в этом
окружении). Caddyfile валидирован; на пилоте сертификат выпустится при
корректном A/AAAA и доступных 80/443 (или proxied 8080/8443).
