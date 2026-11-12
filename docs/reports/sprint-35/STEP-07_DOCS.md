# S35-007 — документация и закрытие спринта

**Дата:** 2026-11-12
**Спринт:** 35 (Observability & Monitoring)
**Статус:** завершено

## Обновлено

- `docs/MONITORING.md` — архитектура, быстрый старт (prod + профиль
  monitoring), порты/UI, метрики, Prometheus/Grafana/Loki, Sentry и PII,
  лимиты и логи, таблица алертов с runbook, troubleshooting, ограничения
  одного узла.
- `docs/SLO.md` — новый документ (S35-006).
- `docs/PRIVACY.md` §7 — мониторинг и Sentry (какие данные, основание,
  отключение).
- `docs/RULES.md` §11.50 — метрики-события, `/metrics` только внутри,
  алерты как код, Sentry/логи без PII, лимиты, SLO/runbook.
- `docs/DESIGN_ADMIN_AND_OPS.md` §10 — 2 воркера/multiprocess, новые метрики,
  стек мониторинга, список алертов.
- `docs/CI.md` — job **Monitoring config**.
- `docs/CHANGELOG.md` — раздел `[0.6.0]` дополнен S35.
- `docs/RELEASES.md` — спринт 35 `[x]`.
- `TODO_V0.4.md` — спринт 35 закрыт, статусы задач и журнал плана.
- `README.md`, `docs/README.md` — ссылки на SLO/MONITORING.
- `.env.example`, `docker-compose.prod.yml` — `UVICORN_WORKERS`,
  `PROMETHEUS_MULTIPROC_DIR`, `METRICS_ENABLED`, `SENTRY_*`.
- `docs/reports/sprint-35/` — отчёты шагов и `SPRINT-35.md`.

## i18n

Новых пользовательских строк нет: Sentry/метрики не меняют UI. Ошибки 429 и
серверные сообщения уже локализованы на русском.

## Проверки

- `promtool check config/rules` — SUCCESS (14 alerts, 7 recording rules).
- `docker compose ... config --quiet` — валидно.
- Стек Prometheus/Grafana/Loki фактически запускался; Grafana provisioning и
  дашборд подтверждены через API.
- Тесты: `test_metrics_export` (15), `test_sentry` (6),
  `test_monitoring_config` (5).
