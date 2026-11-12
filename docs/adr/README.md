# Architecture Decision Records (ADR)

Решения этапа v0.6.0 и ранние ключевые выборы. Формат: **Контекст → Решение →
Последствия** (плюсы/минусы). ADR не переписывается задним числом: при
пересмотре создаётся новый ADR со ссылкой на предыдущий.

## Индекс

| ADR | Решение | Статус |
|-----|---------|--------|
| [ADR-001](0001-ghcr-digest-deploy.md) | GHCR и digest-пиннинг для деплоя | Accepted |
| [ADR-002](0002-caddy-edge.md) | Caddy как edge-сервер (TLS, WS, лимиты) | Accepted |
| [ADR-003](0003-trusted-proxies-refresh-body.md) | TRUSTED_PROXIES и refresh-токен в теле | Accepted |
| [ADR-004](0004-backups-systemd-age-s3.md) | Бэкапы: systemd + age + S3 | Accepted |
| [ADR-005](0005-llm-guardrails.md) | Guardrails LLM для детей | Accepted |
| [ADR-006](0006-secrets-file.md) | Секреты через `*_FILE`/Docker secrets | Accepted |
| [ADR-007](0007-cicd-gates.md) | CI-гейты, preflight и GitFlic merge-gate | Accepted |

## Шаблон

```markdown
# ADR-NNN — Краткое название

**Статус:** Proposed | Accepted | Superseded by ADR-XXX
**Дата:** YYYY-MM-DD
**Контекст:** …

## Решение
…

## Последствия
**Плюсы:**
- …
**Минусы/риски:**
- …
**Ссылки:** …
```
