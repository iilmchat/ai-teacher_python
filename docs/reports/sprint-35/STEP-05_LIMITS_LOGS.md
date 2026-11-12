# S35-005 — лимиты ресурсов и ротация логов

**Дата:** 2026-11-12
**Спринт:** 35 (Observability & Monitoring)
**Статус:** завершено

## Лимиты (`docker-compose.prod.yml`)

| Сервис | `mem_limit` | `cpus` |
|--------|-------------|--------|
| backend | 2g | 2.0 |
| postgres | 1g | 1.0 |
| redis | 128m | 0.5 |
| frontend | 256m | 0.5 |

Профиль мониторинга (`docker-compose.monitoring.yml`): Prometheus 512m/0.5,
Grafana 256m/0.5, Loki 256m/0.5, Promtail 128m/0.25.

## Логи

```yaml
x-logging: &default-logging
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
```

Подключено ко всем сервисам prod и monitoring. Loki retention — 7 дней.
Политика отсутствия PII — `RULES.md` §11.50, `PRIVACY.md` §7.

## Проверка

- `docker compose ... config --quiet` — конфигурация валидна.
- Лимит применён (Prometheus):

```
ai-teacher_python-prometheus-1  19.14MiB / 512MiB  0.11%
```

- `docker stats` для backend/postgres/redis под нагрузкой не снимался: в
  окружении разработки нет прод-нагрузки. Лимиты заданы декларативно и
  проверяются `docker stats` на пилоте (команда — `docs/MONITORING.md` §5).

## Замечание

Использованы `mem_limit`/`cpus` (compose v2, без swarm). `deploy.resources`
не подходит для `docker compose up` без swarm-режима.
