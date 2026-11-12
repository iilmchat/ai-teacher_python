# ADR-002 — Caddy как edge-сервер

**Статус:** Accepted
**Дата:** 2026-11-12
**Контекст:** В v0.5.0 frontend-nginx был публичным, TLS/ACME и единой точки
входа не было; security headers дублировались, WebSocket проксировался nginx.
Нужен TLS «из коробки», автоматический ACME, WebSocket и удобные лимиты.

## Решение

- Единственный публичный сервис — **Caddy** (`deploy/caddy/Caddyfile`):
  - автоматический TLS Let's Encrypt для `$DOMAIN`;
  - `/api/*` → `backend:8000` (WebSocket upgrade автоматически);
  - остальное → `frontend:80` (SPA);
  - HSTS только на HTTPS; CSP/XFO/nosniff/Referrer/Permissions/COOP/CORP;
  - `request_body { max_size 10MB }`, upstream timeouts, `flush_interval -1`
    для LLM-стрима.
- frontend/backend/БД/Redis не публикуют порты; frontend только `expose: 80`.
- Пилот: Caddy на 8080/8443 за внешним прокси (решение владельца), публичный
  prod — отдельный VPS на 80/443.

## Последствия

**Плюсы:**
- один edge и один TLS-слой; сертификаты обновляются автоматически;
- WebSocket и SSE/стриминг без ручной настройки nginx;
- лимиты/таймауты и заголовки безопасности в одном месте.

**Минусы/риски:**
- новый компонент (Caddy) в эксплуатации; ACME требует DNS/80/443;
- при смене домена/портов — правка Caddyfile и перезапуск;
- nginx внутри frontend остаётся для статики (двойной слой, но не публичный).

**Ссылки:** `deploy/caddy/Caddyfile`, `docker-compose.prod.yml`,
`docs/RUNBOOK.md` §4, `docs/PERFORMANCE.md` §4.
