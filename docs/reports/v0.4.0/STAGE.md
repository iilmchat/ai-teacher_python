# Итог этапа v0.6.0 «Production Hardening»

**Дата:** 2026-11-12
**Фактический тег:** `v0.6.0` (создан 2026-11-12; GitHub Release и GHCR)
**Предыдущий релиз:** `v0.5.0` (2026-11-10)
**Каталог отчёта:** `docs/reports/v0.4.0/` — историческое имя, чтобы не
плодить сущности; документ описывает этап **v0.6.0**.

---

## 1. Что вошло в этап

| Спринт | Тема | Итог |
|--------|------|------|
| 33 | Supply chain & repo hygiene | частично: digest-пиннинг, non-root, SBOM/provenance в publish; pre-commit/hadolint/trivy — отклонение |
| 34 | Auth & Edge Hardening | `is_active` в RBAC, refresh в теле, `TRUSTED_PROXIES`, лимиты, fail-fast `SECRET_KEY`, `DOCS_ENABLED` |
| 35 | Observability & Monitoring | 2 воркера + multiprocess-метрики, Sentry без PII, Prometheus/алерты/Grafana/Loki, SLO, лимиты ресурсов |
| 36 | Registry, Deploy, TLS & Backup/DR | GHCR + digest, Caddy/TLS, one-shot migrate, deploy/rollback, бэкапы age/S3/systemd, restore drill |
| 37 | CI Gates & GitFlic | preflight, coverage 70%, паритет CI, `gates.sh/ps1`, GitFlic merge-gate; активация — владелец (`KI-023`) |
| 38 | Security & Privacy | ASVS L1, аудит, DPIA, `*_FILE`-секреты, CSP/HSTS, guardrails LLM |
| 39 | Performance & Capacity | nightly health/tasks/submit, baseline-заготовка, query-count N+1, кэш `/admin/quality`, лимиты/таймауты |
| 40 | DX & Docs | ADR-001…007, CONTRIBUTING/CODEOWNERS/шаблоны, env-drift, актуализация docs |
| 41 | Release v0.6.0 | версия 0.6.0, UPGRADE/релиз-ноты, полные гейты, dry-run отката, отчёты |

---

## 2. Готовность

**Закрытый пилот (single-node) — допустим.** Согласно
[DEVOPS_AUDIT_2026-11.md](../DEVOPS_AUDIT_2026-11.md), блокеры аудита закрыты:
воспроизводимый артефакт/registry, TLS/Caddy, автоматические бэкапы age/S3,
refresh вне query, trusted proxies и per-user лимиты, `is_active` в RBAC,
наблюдаемость и guardrails. Продукт можно запускать для ограниченной группы
пользователей на одном VPS при выполнении RUNBOOK.

**Публичный production — не разрешён.** Нужны:
- отдельный VPS/домен и юридическая проверка 152-ФЗ;
- multi-node/HA и DR-SLO 2.0 (вне этапа, D-001);
- e-mail-подтверждение/сброс пароля (`KI-035`, v0.7.0);
- полная модерация ответов LLM (`KI-036`, v0.7.0);
- активация required checks GitFlic/GitHub (`KI-023`, владелец).

---

## 3. Метрики

| Показатель | Значение |
|------------|----------|
| Backend `pytest` | **834 passed, 1 skipped**; coverage **79.17%** (порог 70) |
| Ruff / MyPy strict | **0 / 0** (104 файла) |
| Frontend unit (Vitest) | **279 passed** (47 файлов) |
| E2E (Playwright) | **37 passed, 1 skipped** (2.7 мин) |
| Миграции | head **022** (22 миграции); `alembic check` — чисто; новых в v0.6.0 нет |
| Env-drift | `Settings` 76 полей ↔ `.env.example` — OK |
| GHCR | 3 образа (`backend`, `frontend`, `sandbox-runner`) по тегу `v0.6.0` и digest |
| GitHub Release | <https://github.com/iilmchat/ai-teacher_python/releases/tag/v0.6.0> |
| Версия | `0.6.0` в pyproject/package/config — 0 расхождений |
| Откат | `rollback.sh --dry-run` — exit 0 |
| Известные проблемы | 35 записей: 6 активных, 29 закрытых |

---

## 4. Отклонения от плана

1. **S33** закрыт частично: S33-001/002 (digest, non-root) и SBOM/provenance
   в publish есть; pre-commit, hadolint/trivy-job и отдельные checksums не
   внедрялись. Принято как отклонение; supply-chain-риск снижен digest-пиннингом
   и Dependabot.
2. **S37** — GitFlic required checks не активированы: нужен доступ владельца
   (`KI-023`); скрипт/инструкция готовы.
3. **GHCR publish** выполнен по тегу `v0.6.0`: три образа опубликованы и
   проверены по digest ([digests](../../releases/v0.6.0-digests.txt)).
   **Staging-деплой** не выполнялся — нет стенда/домена; workflow готов.
   Digest-артефакт в Actions упал из-за скрытого `.digests` (исправлено в
   `docker-publish.yml` для будущих релизов), образы не затронуты.
4. **Restore drill** проверялся в S36; в S41 выполнен dry-run отката, реальный
   restore не запускался (нет свежего прод-бэкапа в сессии).
5. **Perf baseline** (`measured: null`) ждёт первого nightly-прогона на
   self-hosted runner.
6. **Онбординг на чистой машине** остаётся ручной проверкой (S40).

---

## 5. Известные проблемы (активные)

- `KI-023` — merge-gate/required checks GitHub Free/GitFlic (владелец).
- `KI-027` — access-токен не отзывается, JWT в localStorage; httpOnly/BFF —
  v0.7.0.
- `KI-035` — e-mail-подтверждение/сброс пароля отложены.
- `KI-036` — полная модерация ответов LLM.
- `KI-031` — остаточные API-only маршруты.
- `KI-018` — `.format()` в песочнице (принятый остаток).

Полный реестр — [KNOWN_ISSUES.md](../../KNOWN_ISSUES.md).

---

## 6. Уроки

- **Безопасность дешёвая в начале:** `is_active`/refresh/trusted proxy заняли
  часы, но закрыли High-риски аудита; откладывание стоило бы дороже.
- **Инфраструктура как код работает:** Caddy/GHCR/systemd/бэкапы проверяемы
  в репозитории и не требуют «памяти» эксплуататора.
- **Тесты против N+1 и env-drift** ловят классы ошибок, которые code review
  пропускает; оба гейта дешёвы и обязательны.
- **Честные границы:** single-node закрытый пилот — да; публичный production —
  нет. Разделение зафиксировано в релиз-нотах и аудите.
- **Бюрократия тега:** без утверждения владельцем тег не ставится, поэтому
  релизный workflow и артефакты проверяются отдельно после approval.

---

## 7. Следующий этап

**v0.7.0 «Engagement, Accessibility & Auth Hardening»** (спринты 49–52,
[TODO_V0.7.md](../../../TODO_V0.7.md)): траектории/вовлечение, доступность и PWA,
перенос токенов в httpOnly-cookie/BFF (`KI-027`), релиз v0.7.0. Перед стартом —
выполнить post-release smoke на staging/пилоте и зафиксировать digest в
`.env.prod`; тег `v0.6.0` уже создан и опубликован.
