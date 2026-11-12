# ADR-003 — TRUSTED_PROXIES, refresh в теле, is_active в RBAC

**Статус:** Accepted
**Дата:** 2026-11-12
**Контекст:** Аудит v0.5.0: `X-Forwarded-For` можно подделать и обойти rate
limit; refresh-токен передавался в query string (утечка в access-логи);
деактивированный teacher/admin сохранял доступ (`require_role` не проверял
`is_active`).

## Решение

1. **Клиентский IP** — единый `client_ip(request)` (`app/core/ip_utils.py`):
   - `TRUSTED_PROXIES` — список IP/CIDR (в prod — подсеть Docker Caddy);
   - XFF учитывается только от доверенного TCP-peer;
   - разбор справа налево, доверенные хопы пропускаются, первый недоверенный —
     клиент; пустой список = доверять только peer.
2. **Refresh-токен** — только тело JSON `POST /auth/refresh`
   (`RefreshTokenRequest`), query-вариант удалён; `Cache-Control: no-store`.
3. **RBAC** — `require_role` зависит от `get_current_active_user`:
   деактивированный пользователь получает 401 даже с валидным access-токеном.

## Последствия

**Плюсы:**
- подделка XFF не расширяет лимиты и не «размазывает» аудит;
- токены не попадают в access-логи/историю прокси;
- деактивация действует сразу, без ожидания TTL токена.

**Минусы/риски:**
- breaking change для клиентов refresh (обновлён frontend/UPGRADE);
- неверный `TRUSTED_PROXIES` схлопывает IP — нужен smoke после деплоя;
- 401 вместо 403 для деактивированных (ожидаемо, не раскрываем аккаунт).

**Ссылки:** `app/core/ip_utils.py`, `app/core/rate_limiter.py`,
`app/api/v1/auth.py`, `app/core/security.py`, `docs/RULES.md` §11.49.
