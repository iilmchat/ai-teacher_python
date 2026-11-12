# S34-003 — TRUSTED_PROXIES и client_ip

**Дата:** 2026-11-11
**Спринт:** 34 (P0: Auth & Edge Hardening)
**Статус:** завершено
**Закрывает:** KI-034 (High)

## Проблема

`RateLimitMiddleware` брал первый IP из `X-Forwarded-For` без проверки
источника. Атакующий менял заголовок и получал новый ключ лимита. Тот же
небезопасный разбор использовался в аудите.

## Алгоритм

Единая функция `app/core/ip_utils.py::client_ip(request)`:

1. Прямой TCP-peer — `request.client.host`.
2. `TRUSTED_PROXIES` пуст → заголовок игнорируется, возвращается peer.
3. Peer не входит в `TRUSTED_PROXIES` → заголовок подделан, возвращается peer.
4. Peer доверенный → `X-Forwarded-For` разбирается **справа налево**,
   доверенные хопы пропускаются, первый недоверенный IP — клиент.
5. Все хопы доверенные → возвращается самый левый IP.

Поддерживаются одиночные IP и CIDR (`10.0.0.0/8`).

## Изменения

- `backend/app/config.py` — настройка `trusted_proxies: list[str]`.
- `backend/app/core/ip_utils.py` — новый модуль `client_ip`/`_is_trusted_proxy`.
- `backend/app/core/rate_limiter.py` — `RateLimitMiddleware` использует
  `client_ip`; собственный `_client_ip` удалён.
- `backend/app/services/audit_service.py` — `client_ip` делегирует общему
  резолверу (обрезает до 64 символов).
- `backend/tests/test_rate_limit.py` — 8 новых тестов:
  - без `TRUSTED_PROXIES` заголовок игнорируется;
  - доверенный peer → клиент из заголовка;
  - недоверенный peer → заголовок отбрасывается;
  - пропуск доверенных хопов справа налево;
  - CIDR;
  - отсутствие заголовка;
  - подмена XFF не обходит лимит (без доверенных прокси);
  - подмена левой части заголовка за доверенным прокси не обходит лимит.

## Проверки

```
cd backend && python -m pytest tests/test_rate_limit.py -q   # 23 passed
```

## Эксплуатация

`TRUSTED_PROXIES` должен содержать адреса Caddy/nginx (например,
`127.0.0.1` для локального прокси на том же хосте). Пустой список безопасен,
но тогда за прокси все клиенты будут иметь IP прокси. Описано в
`SECURITY.md`, `SPEC.md` §3.12, `RULES.md` §11.49 и `.env.example`.
