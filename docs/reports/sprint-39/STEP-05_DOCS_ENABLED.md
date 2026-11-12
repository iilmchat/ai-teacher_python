# S39-005 — DOCS_ENABLED и документация

**Дата:** 2026-11-12
**Спринт:** 39
**Статус:** завершено

## DOCS_ENABLED

- `DOCS_ENABLED=false` в prod-compose (S34-006); FastAPI не регистрирует
  `/api/docs`, `/api/redoc`, `/api/openapi.json`.
- Тест `tests/test_security_settings.py` проверяет 404; контрактный снапшот
  строится из `app.openapi()` в тестах, на рантайм-нагрузку не влияет.
- Caddy проксирует `/api/*`, но маршрутов docs в backend нет; отдельного
  лимита не требуется. Проверено `test_deploy_config.py`
  (`DOCS_ENABLED == "false"`).

## Документация

- `docs/PERFORMANCE.md` — сценарии, baseline, N+1, кэш, лимиты/таймауты.
- `docs/CAPACITY.md` — методика, оценки, рекомендации.
- `docs/ARCHITECTURE.md` — кэш качества и раздел 6.2.1 про лимиты.
- `docs/RULES.md` §11.52 — значения лимитов/таймаутов.
- `docs/PERFORMANCE.md` §1 — локальный smoke (не baseline).
- `docs/reports/sprint-39/` — отчёты.
