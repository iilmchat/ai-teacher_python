# SPRINT-26.md — Export, Retention & Privacy (v0.3.0)

**Период:** 2026-11-01  
**Задачи:** S26-001…S26-005  
**Статус:** ✅ экспорт аналитики и отчёт класса, retention-скрипт, удаление
аккаунта с анонимизацией, `docs/PRIVACY.md`; ⚠️ UI-кнопка отчёта — остаток

---

## 1. Файлы (+/-)

```
+ backend/app/services/export_service.py     — CSV/JSON-потоки, 4 набора
+ backend/app/services/class_report.py       — CSV-матрица класса
+ backend/scripts/apply_retention.py         — retention (--dry-run/--only/батчи)
+ backend/alembic/versions/20261031_0012_user_is_active.py
+ backend/tests/test_export_retention.py     — 12 тестов
+ docs/PRIVACY.md                            — политика ПДн
+ docs/reports/sprint-26/SPRINT-26.md        — этот отчёт
~ backend/app/api/v1/admin.py                — GET /admin/analytics/export
~ backend/app/api/v1/classrooms.py           — GET /{id}/report
~ backend/app/api/v1/auth.py                 — DELETE /auth/me
~ backend/app/core/security.py               — is_active → 401
~ backend/app/models/user.py                 — is_active
~ backend/app/schemas/user.py                — DeleteAccountRequest
~ backend/app/config.py                      — RETENTION_*, EXPORT_MAX_ROWS
~ docs: SPEC §16, DESIGN_ADMIN_AND_OPS §11, RULES §11.23, USER_GUIDE,
  CHANGELOG, RELEASES, TODO
```

---

## 2. Покрытие

12 тестов (`tests/test_export_retention.py`):

- **Экспорт:** users CSV (заголовки, Content-Disposition), tasks JSON
  (`dataset`, `items`), 403 ученику, 422 на неизвестный dataset.
- **Отчёт класса:** CSV с задачей и `overdue=no`, строка «ИТОГО»; 403 ученику.
- **Retention:** cutoff `0` → `None`; cutoff 30 дней; состав таблиц; CLI
  `--dry-run --only notifications` → exit 0.
- **Удаление аккаунта:** неверный пароль → 400; после удаления — 401 на `/me`
  и на логин; запись `user.self_deleted` видна админу; admin-delete работает.

Непокрытое: UI-кнопка (нет), cron-запуск retention (инфраструктура),
граничный случай `EXPORT_MAX_ROWS` с 100k+ строк (проверяется вручную).

---

## 3. Результаты

| Проверка | Результат |
|----------|-----------|
| `ruff check app tests scripts` | 0 |
| `mypy app` (strict) | 0 |
| Sprint 26 тесты | **12 passed** |
| Полный backend | **485 passed + 1 skipped** (см. RELEASES) |
| `alembic upgrade/check` | OK (012) |

---

## 4. Smoke

1. `GET /api/v1/admin/analytics/export?dataset=users&format=csv` (admin) →
   скачивание CSV; в `audit_log` появляется `analytics.exported`.
2. Создать класс + назначение, вступить учеником → `GET /classrooms/{id}/report`
   → CSV с матрицей и строкой «ИТОГО»; под учеником → 403.
3. `python backend/scripts/apply_retention.py --dry-run` → счётчики, ничего не
   удалено.
4. `DELETE /api/v1/auth/me {"password": "..."}` → 204; логин тем же паролем →
   401; в `/admin/audit` — `user.self_deleted`.

---

## 5. Что не так

1. **UI-кнопка «Скачать отчёт»** не сделана в этом заходе — API готов; S26-002
   остаётся `[~]` до небольшого фронтенд-коммита.
2. **Retention не автоматизирован в compose** — скрипт запускается вручную или
   по cron (пример в DESIGN_ADMIN_AND_OPS §11); умышленно, чтобы не удалять
   данные без решения эксплуатации.
3. **Потоковый экспорт использует сессию запроса** — сначала генератор открывал
   свою сессию, но на per-test event loop это давало «Event loop is closed»;
   сессия запроса живёт до конца стриминга (проверено тестами).
4. **Self-service экспорт ученика** отсутствует: запрос через администратора
   (зафиксировано в PRIVACY.md).

---

## 6. Новые KI

Нет.

---

## 7. Обоснование

1. **Серверный курсор, а не `fetchall`.** Экспорт 100k строк не должен поднимать
   память API; `db.stream()` отдаёт строки по мере чтения.
2. **Лимит строк, а не таймаут.** Пользователю нужен предсказуемый результат:
   `X-Export-Limit` и аудит с параметрами лучше, чем «зависло и упало».
3. **CSV с BOM.** Отчёты открывают в Excel — без `utf-8-sig` кириллица ломается.
4. **Retention отдельным скриптом.** Удаление исторических данных в API-запросе
   конкурировало бы за блокировки с пользовательскими операциями; batch-скрипт
   с `--dry-run` безопаснее и проще для cron.
5. **Анонимизация вместо каскадного удаления.** История прогресса нужна классу и
   учителю; замена PII-полей сохраняет аналитику и выполняет требование
   «удалить аккаунт», не ломая отчёты задним числом.
