# Спринт 34 — Auth & Edge Hardening (v0.6.0, P0)

**Дата:** 2026-11-11
**Этап:** v0.6.0 «Auth & Edge Hardening» (план `TODO_V0.4.md` пересобран)
**Задачи:** S34-001…S34-007
**Статус:** завершён
**Тесты:** backend **754 passed, 1 skipped**; frontend `api.test.ts` — 6 passed

---

## 1. Решения владельца §10

| № | Вопрос | Решение |
|---|--------|---------|
| 1 | Версия релиза | **v0.6.0**; `TODO_V0.6.md` → `TODO_V0.7.md` |
| 2 | Multi-node | вынесен за границы этапа |
| 3 | Registry | **GHCR** |
| 4 | Пилот | текущий VPS, наш Caddy на **8080/8443**; публичный prod — отдельный VPS |
| 5 | E-mail | отложен, заведён **KI-035** (v0.7.0) |

Зафиксировано в `TODO_V0.4.md` §0.0 и журнале плана.

---

## 2. Реестр проблем

| KI | Severity | Тема | Итог |
|----|----------|------|------|
| KI-032 | High | `require_role` не проверяет `is_active` | **Closed** (S34-001) |
| KI-033 | High | `refresh_token` в query string | **Closed** (S34-002) |
| KI-034 | High | обход rate-limit через `X-Forwarded-For` | **Closed** (S34-003) |
| KI-035 | Med | нет подтверждения e-mail и сброса пароля | **Open**, v0.7.0 |

---

## 3. Изменения по задачам

### S34-001 — require_role и is_active
`role_checker` зависит от `get_current_active_user`; деактивированный
teacher/admin получает `401` даже с валидным токеном. Регресс-тесты для обеих
ролей (inactive → 401, active → 200).

### S34-002 — refresh_token в теле JSON
`POST /auth/refresh` принимает `RefreshTokenRequest` (`{"refresh_token": ...}`).
Обновлены бэкенд-тесты, `frontend/src/lib/api.ts` (`refreshAccessToken`),
frontend-тест. Breaking change описан в `UPGRADE.md` §0.5 и `CHANGELOG.md`.

### S34-003 — TRUSTED_PROXIES и client_ip
Новый `app/core/ip_utils.py`: заголовок учитывается только от доверенного
TCP-peer, разбор справа налево, CIDR. `rate_limiter` и `audit_service`
переведены на единый резолвер. 8 тестов, включая попытки подмены XFF.

### S34-004 — лимиты refresh и песочницы
`/auth/refresh` — 30/мин на IP отдельным ключом; `/code/execute` — 30/мин на
пользователя. 6 тестов: блокировка, изоляция, флаг, fail-open.

### S34-005 — fail-fast SECRET_KEY
`validate_security_settings()` в `lifespan`: при `DEBUG=false` дефолтный или
короткий (<32) ключ прерывает старт (`InsecureSettingsError`).

### S34-006 — DOCS_ENABLED
Флаг `docs_enabled` (default true). При `false` Swagger/ReDoc/OpenAPI не
регистрируются. Тесты проверяют 404/200.

### S34-007 — документация и i18n
Обновлены `SECURITY.md`, `SPEC.md`, `RULES.md` (§11.49), `UPGRADE.md`,
`CHANGELOG.md`, `KNOWN_ISSUES.md`, `README.md`, `docs/README.md`,
`docs/RELEASES.md`, `TODO_V0.4.md`, `TODO_V0.5.md`, `.env.example`; версия —
`0.6.0`. Новых UI-строк нет — правки i18n не требуются.

---

## 4. Файлы

**Код (backend):**
- `app/core/security.py` — `require_role` на `get_current_active_user`;
- `app/api/v1/auth.py` — `RefreshTokenRequest`, refresh через тело;
- `app/core/ip_utils.py` — новый модуль `client_ip`;
- `app/config.py` — `trusted_proxies`, `docs_enabled`, версия `0.6.0`,
  `validate_security_settings`, `InsecureSettingsError`;
- `app/core/rate_limiter.py` — единый `client_ip`, refresh-лимит,
  `CODE_EXECUTE_LIMIT`;
- `app/api/v1/code.py` — per-user лимит `/code/execute`;
- `app/services/audit_service.py` — общий `client_ip`;
- `app/main.py` — fail-fast в `lifespan`, `docs_urls`/`DocsConfig`.

**Тесты (backend):**
- `tests/test_auth.py` — +4 регресса `require_role`, refresh на JSON;
- `tests/test_rate_limit.py` — +14 тестов (XFF, refresh, per-user);
- `tests/test_security_settings.py` — новый файл, 8 тестов;
- `tests/test_password_change.py`, `tests/test_sessions.py`,
  `tests/test_profile_selfservice.py` — refresh на JSON.

**Frontend:**
- `src/lib/api.ts` — refresh POST с JSON-телом;
- `src/test/api.test.ts` — проверка тела refresh;
- `package.json` — версия `0.6.0`.

**Документация:** `SECURITY.md`, `docs/SPEC.md`, `docs/RULES.md`,
`docs/UPGRADE.md`, `docs/CHANGELOG.md`, `docs/KNOWN_ISSUES.md`,
`docs/RELEASES.md`, `README.md`, `docs/README.md`, `TODO_V0.4.md`,
`TODO_V0.7.md` (переименован), `TODO_V0.5.md`, `.env.example`, `pyproject.toml`,
отчёты `docs/reports/sprint-34/`.

---

## 5. Проверки

```
cd backend && python -m pytest -q
# 754 passed, 1 skipped

cd backend && python -m ruff check app tests      # All checks passed
cd backend && python -m mypy <изменённые модули>  # Success: no issues found
cd frontend && pnpm exec vitest run src/test/api.test.ts   # 6 passed
```

---

## 6. Остаточные риски и следующий шаг

- `KI-035` (e-mail подтверждение и сброс пароля) — v0.7.0.
- `KI-027` (httpOnly-cookie/BFF) — v0.7.0, спринт 51.
- `KI-023` (merge-gate) — действие владельца (GitFlic-токен или GitHub Pro).
- `TRUSTED_PROXIES` на пилоте должен содержать адрес Caddy; публичный prod —
  отдельный VPS (решение владельца).
