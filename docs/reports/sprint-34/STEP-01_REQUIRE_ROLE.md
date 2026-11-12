# S34-001 — require_role и is_active

**Дата:** 2026-11-11
**Спринт:** 34 (P0: Auth & Edge Hardening)
**Статус:** завершено
**Закрывает:** KI-032 (High)

## Проблема

`require_role` использовал `get_current_user`, который не проверяет
`users.is_active`. Деактивированный teacher/admin сохранял доступ к
защищённым эндпоинтам при валидном access-токене.

## Изменения

- `backend/app/core/security.py` — `role_checker` теперь зависит от
  `get_current_active_user` вместо `get_current_user`.
- `backend/tests/test_auth.py` — регресс-тесты:
  - `test_teacher_role_rejects_inactive_user` — teacher с `is_active=false`
    получает `401` («Аккаунт удалён») на `/api/v1/teacher/tasks`;
  - `test_admin_role_rejects_inactive_user` — admin с `is_active=false`
    получает `401` на `/api/v1/admin/users`;
  - `test_teacher_role_allows_active_user`, `test_admin_role_allows_active_user`
    — контроль: активные пользователи получают `200`.

## Проверки

```
cd backend && python -m pytest tests/test_auth.py -q
# 21 passed
```

Полный смежный прогон: `test_auth`, `test_rate_limit`, `test_security_settings`,
`test_code_api`, `test_contract_openapi` — **75 passed**.

## Влияние на контракт

Поведение меняется ожидаемо: деактивированный пользователь получает `401`
вместо прежнего `403`. Отражено в `UPGRADE.md` §0.5 и `RULES.md` §11.49.
