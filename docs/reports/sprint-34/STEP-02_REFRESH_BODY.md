# S34-002 — refresh_token в теле запроса

**Дата:** 2026-11-11
**Спринт:** 34 (P0: Auth & Edge Hardening)
**Статус:** завершено
**Закрывает:** KI-033 (High)

## Проблема

`POST /auth/refresh` принимал `refresh_token` в query string
(`?refresh_token=...`). Токен попадает в access-логи reverse-proxy, историю
браузера и системы логирования.

## Изменения

- `backend/app/api/v1/auth.py` — добавлена схема `RefreshTokenRequest`
  (`refresh_token: str`), эндпоинт принимает её телом JSON и отдаёт
  `Cache-Control: no-store`.
- `backend/tests/test_auth.py` — все вызовы refresh переведены на
  `json={"refresh_token": ...}` (`test_refresh_token`,
  `test_refresh_with_access_token_rejected`,
  `test_refresh_rejected_for_inactive_user`,
  `test_refresh_rejected_after_account_deletion`).
- `frontend/src/lib/api.ts` — `refreshAccessToken` отправляет
  `POST /auth/refresh` с `Content-Type: application/json` и телом
  `{ refresh_token }`.
- `frontend/src/test/api.test.ts` — проверка, что refresh уходит POST-ом в
  `/api/v1/auth/refresh` с JSON-телом, а не в query.
- `docs/UPGRADE.md` §0.5, `docs/CHANGELOG.md` — breaking change описан.

## Проверки

```
cd backend && python -m pytest tests/test_auth.py -q      # 21 passed
cd frontend && pnpm exec vitest run src/test/api.test.ts  # 6 passed
```

## Breaking change

Клиенты, использующие `?refresh_token=`, получат `422` (обязательное поле
тела). Миграция — одна строка: передавать токен в JSON. См. `UPGRADE.md` §0.5.
