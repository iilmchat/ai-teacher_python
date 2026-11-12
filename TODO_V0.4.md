# TODO_V0.4.md — план этапа v0.6.0 «Production Hardening»

> ## ⚠️ План обновлён 2026-11-11
>
> Учтены **выводы DevOps-аудита ноября 2026**
> ([docs/reports/DEVOPS_AUDIT_2026-11.md](docs/reports/DEVOPS_AUDIT_2026-11.md))
> и **реалии v0.5.0**: базис этапа — не v0.3.3, а тег `v0.5.0` (спринты 42–48,
> 2026-11-10). Этап v0.4.0 официально **возобновлён** после паузы по D-001 и
> переставлен по приоритетам аудита:
>
> 1. сначала High-риски авторизации, токенов и лимитов (спринт 34) — они дают
>    прямой обход прав и защит, пока не начат деплой;
> 2. затем подключённая наблюдаемость: scrape, Sentry, алерты, лимиты
>    ресурсов (спринт 35);
> 3. затем воспроизводимый артефакт и периметр: GHCR, digest, Caddy/TLS,
>    деплой/откат, автоматические бэкапы и DR (спринт 36);
> 4. затем гейты, безопасность/приватность, производительность, DX и релиз
>    (37–41).
>
> **Multi-node вынесен за границы этапа** (§9): аудиту и закрытому пилоту он не
> нужен, а «устойчивый production» по аудиту упирается в registry, TLS, бэкапы
> и мониторинг, а не в число реплик. Это осознанное сужение, а не забытый пункт.
>
> ## ✅ Решения владельца (2026-11-11)
>
> 1. Версия релиза — **v0.6.0**; `TODO_V0.6.md` сдвинут на `TODO_V0.7.md`.
> 2. Multi-node — вынесен за границы этапа.
> 3. Container registry — **GHCR**.
> 4. Пилот — **текущий VPS**, наш Caddy на портах **8080/8443**; для публичного
>    прода — отдельный VPS.
> 5. E-mail — отложен, заведён `KI-035` (подтверждение e-mail и сброс пароля,
>    v0.7.0).
>
> Спринт 34 (P0: Auth & Edge Hardening) **завершён** 2026-11-11.

> Этап 4 по реестру решений (D-001), исторически — продолжение
> [TODO_V0.3.md](TODO_V0.3.md) (v0.3.x «Ops & Scale»).
> Правила — [docs/RULES.md](docs/RULES.md), контракты — [docs/SPEC.md](docs/SPEC.md),
> реестр проблем — [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md),
> журнал спринтов — [docs/RELEASES.md](docs/RELEASES.md).
>
> Статусы задач: `[ ]` — не начата, `[~]` — в работе, `[x]` — выполнена,
> `[!]` — заблокирована (см. `KI-NNN`).

**Целевая версия:** v0.6.0 (утверждена 2026-11-11)  
**Создан:** 2026-11-02 · **Обновлён:** 2026-11-11 — план пересобран и утверждён; спринт 34 закрыт  
**Базис:** `v0.5.0` (2026-11-10), ветка `main`, 22 миграции  
**Статус:** в работе — спринт 34 `[x]` завершён; спринты 35–41 по плану  
**Оценка этапа:** ~29 инженерных дней (оценки ±30%, без ожидания доступов)  
**Следующий свободный KI:** `KI-036`  
**Следующий этап:** [TODO_V0.7.md](TODO_V0.7.md) — v0.7.0 «Engagement,
Accessibility & Auth Hardening»

---

## 0.0. Решения владельца по пересборке (2026-11-11)

| № | Вопрос | Решение |
|---|--------|---------|
| 1 | Версия релиза | **v0.6.0**; `TODO_V0.6.md` → `TODO_V0.7.md` |
| 2 | Multi-node | **вынесен за границы этапа** — не входит в v0.6.0 |
| 3 | Container registry | **GHCR** (GitHub Container Registry) |
| 4 | Пилот | **текущий VPS**, наш Caddy на портах **8080/8443**; для публичного прода — **отдельный VPS** |
| 5 | E-mail | **отложен**, заведён `KI-035` (подтверждение e-mail и сброс пароля — v0.7.0) |

**Приоритет этапа:** P0 — Auth & Edge Hardening (спринт 34), затем остальные
спринты плана. Multi-node/HA/DR исключены из критериев приёмки v0.6.0.

---

## 0. Цель этапа

v0.3.x сделал продукт эксплуатируемым на одном узле, v0.5.0 закрыл продуктовое
ядро. v0.4.0 — это **production hardening по фактам аудита**: воспроизводимый
артефакт в registry, закрытый TLS-периметр, автоматические бэкапы с off-site и
проверенным восстановлением, подключённые метрики/трейсы/ошибки с алертами как
кодом, закрытые High-риски авторизации и лимитов, честный merge-gate.

### 0.1. Критерии успеха этапа

| Критерий | Проверяемое доказательство |
|----------|-----------------------------|
| Воспроизводимый артефакт | образы `ghcr.io/...` по digest; на сервере **нет** сборки из исходников; деплой = pull по digest |
| Периметр | HTTPS-домен, Caddy терминирует TLS, `:3000` на хост не публикуется, HSTS только по TLS |
| Восстановление | systemd-таймер + `age` + S3 (Selectel), метрика `backup_last_success_timestamp`, restore drill зелёный |
| Наблюдаемость | scrape `/metrics`, Prometheus + Grafana + Loki, Sentry, алерты и SLO — в репозитории, поднимаются одной командой |
| High-риски закрыты | деактивированный teacher/admin получает 403; refresh только в теле; подделка `X-Forwarded-For` не расширяет лимит |
| Устойчивость | лимиты CPU/RAM, ротация логов, `SECRET_KEY` fail-fast в prod, лимиты body-size и таймауты |
| Supply chain | все `FROM`/`image:` закреплены; `hadolint`/`trivy` без HIGH/CRITICAL; SBOM в релизе |
| Гейты | красный PR не мержится (или `KI-023` явно `Blocked` с ручным fallback); coverage-гейт |
| Безопасность | ASVS L1 без открытых High; секретов в конфигах нет; публичный Swagger закрыт в prod |
| Документация | ADR, `DEPLOY.md`, `MONITORING.md`, `RUNBOOK.md`, upgrade-гайд, отчёты спринтов |
| Релиз | тег, GitHub/GitFlic Release, SBOM и checksums, проверенный откат |

### 0.2. Принципы этапа

1. **Безопасность раньше удобства деплоя.** Пока `require_role` пускает
   деактивированного учителя, а `refresh_token` утекает в access-логи, никакой
   registry и TLS не делают продукт production-готовым.
2. **Blocker №0 — артефакт, а не архитектура.** Аудит прямо говорит: код
   зрелый, блокируют операции. Поэтому спринт 36 — самый дорогой в этапе.
3. **Сначала измеримость, потом лимиты.** Лимиты CPU/RAM и алерты ставятся
   после scrape: иначе непонятно, что именно ограничивать.
4. **Автоматизация вместо памяти.** Деплой, откат, миграции, бэкап, restore
   drill — команды и таймеры, а не чек-лист «помню, как делал».
5. **Каждый гейт воспроизводится локально.** Проверка, которую нельзя запустить
   одной командой, — не гейт, а пожелание.
6. **Один источник правды.** Детали задач живут здесь; `RELEASES.md` хранит
   только статус и итоги, `KNOWN_ISSUES.md` — проблемы.

---

## 1. Базис: что аудит говорил и что реально в v0.5.0

Проверено по коду `main` на 2026-11-11. Аудит писался до мержа v0.5.0, поэтому
часть пунктов уже неактуальна; это зафиксировано явно, чтобы не «чинить» уже
исправленное и не пропустить оставшееся.

| Пункт аудита | Факт в v0.5.0 | Вывод |
|--------------|---------------|-------|
| «Нет воспроизводимого артефакта: спринт 47 не смержен, ветка отличается от `main`» | `main` содержит спринты 42–48, тег `v0.5.0`, рабочее дерево чистое | Закрыто v0.5.0; остаётся registry (S36-001) |
| «Нет registry/CD/deploy/rollback; на сервере сборка из исходников» | `docker-compose.prod.yml` содержит `build:` для backend/frontend; GHCR в workflows отсутствует | Актуально → S36-001/002/005 |
| «prod отдаёт HTTP на `:3000`, HSTS по HTTP, публикация порта обходит Caddy» | `${HTTP_PORT:-3000}:80`; HSTS задан в `frontend/nginx.conf` независимо от схемы | Актуально → S36-003 |
| «`scripts/backup.sh` привязан к dev-имени `ai_teacher_postgres`» | `CONTAINER="${POSTGRES_CONTAINER:-ai_teacher_postgres}"` — дефолт неверен для prod | Актуально → S36-006 |
| «Refresh-токен в query string» | `refresh_tokens(refresh_token: str, db)` — FastAPI читает это как query-параметр | Актуально → S34-002 (`KI-033`) |
| «`require_role` использует `get_current_user`» | Подтверждено: `backend/app/core/security.py:170`, зависимость от `get_current_user`, без `is_active` | Актуально → S34-001 (`KI-032`) |
| «Обход лимита подделкой `X-Forwarded-For`» | `rate_limiter._client_ip` берёт первый элемент заголовка без проверки источника; то же в `audit_service` | Актуально → S34-003 (`KI-034`) |
| «`SECRET_KEY` по умолчанию не валит старт» | `backend/app/main.py:49` пишет `logger.error`, старт продолжается | Актуально → S34-005 |
| «Мониторинг не подключён: метрики есть, scrape/алертов/дашбордов/Sentry нет» | `/metrics` реализован и скрыт за nginx (404), но Prometheus, Grafana, Loki, Sentry, OTel отсутствуют | Актуально → S35 |
| «Токены в localStorage, logout — no-op, access не отзывается» | `POST /auth/logout` возвращает сообщение и ничего не делает; `token_version` отзывает только refresh (S45-001/005) | Частично: остаток — `KI-027`, перенос в cookie/BFF — v0.7.0 (S51) |
| «Нет e-mail верификации и сброса пароля» | Эндпоинтов восстановления нет; смена пароля и сессии есть (KI-028 закрыт) | Решение — S38-005; при отсутствии SMTP — `KI-035`, v0.6.0 |
| «Нет контент-безопасности LLM для детей / prompt injection» | Есть очередь модерации и метрики качества (S47), guardrails ответов LLM — нет | Решение/обзор — S38-006 |
| «Нет healthcheck в Dockerfile» | Устарело: `HEALTHCHECK` есть и в `backend/Dockerfile:23`, и в `frontend/Dockerfile` | Снять с плана |
| «Один uvicorn-воркер; нет лимитов CPU/RAM и ротации логов» | В prod compose нет `deploy.resources`, `UVICORN_WORKERS` и logging-опций | Актуально → S35-001/005 |
| «Swagger/OpenAPI публичны» | `docs_url="/api/docs"`, `openapi_url` включены безусловно | Актуально → S34-006 |
| «`UploadFile` читается в память без лимита; нет body-size и таймаутов в nginx» | Лимитов в nginx/Caddy нет; таймаутов прокси нет | Актуально → S39-005 |
| «Миграции при каждом старте» | `docker-entrypoint.sh` делает `alembic upgrade head`; `SKIP_MIGRATIONS` поддержан, но prod compose его не задаёт | Актуально → S36-004 |
| «Наивные `datetime.utcnow()` (~1400)» | Присутствуют, в т.ч. `security.py:65` | Технический долг, §9 (не блокирует этап) |
| «README/ARCHITECTURE устарели (538 тестов/013 миграций)» | 22 миграции, тестов заметно больше | Актуально → S40-005 |

**Не является проблемой (сделано и подтверждено):** структурированные логи и
`request_id`, `/health/live|ready`, retention-планировщик с advisory-lock,
экспорт ПДн, digest-пиннинг базовых образов, non-root backend, gitleaks,
pip-audit/pnpm audit, контрактные тесты OpenAPI, e2e Playwright, миграционная
дисциплина (`alembic check`), 6 слоёв песочницы с тестами атак, отзыв
refresh-токенов и `user_sessions`.

---

## 2. Интеграция аудита: находка → спринт → задача

Карта обязательна к исполнению: каждая находка аудита либо имеет задачу, либо
явно вынесена за границы этапа с причиной. Никаких «потом разберёмся».

### 2.1. Blocker'ы аудита

| # | Находка | Куда | Задача |
|---|---------|------|--------|
| B1 | Нет воспроизводимого артефакта (не смержено) | — | Закрыто v0.5.0 (§1) |
| B2 | Нет registry/CD/deploy/rollback | 36 | S36-001 (GHCR), S36-002 (digest), S36-005 (deploy/rollback) |
| B3 | Нет TLS/домена/edge; `:3000` публикуется | 36 | S36-003 (Caddy/TLS, снятие публикации) |
| B4 | Бэкапы не автоматизированы; имя контейнера | 36 | S36-006 (systemd, S3, age, имя контейнера), S36-007 (drill) |

### 2.2. High

| # | Находка | Куда | Задача |
|---|---------|------|--------|
| H1 | `require_role` не проверяет `is_active` | **34** | S34-001 (`KI-032`) |
| H2 | `refresh_token` в query string | **34** | S34-002 (`KI-033`) |
| H3 | Обход rate-limit подделкой `X-Forwarded-For` | **34** | S34-003 (`KI-034`) |
| H4 | Нет лимита на `/auth/refresh`, `/code/execute` — только общий IP-лимит | **34** | S34-004 |
| H5 | `SECRET_KEY` по умолчанию не валит старт | **34** | S34-005 |
| H6 | Swagger/OpenAPI публичны в prod | **34** | S34-006 |
| H7 | Мониторинг не подключён (scrape/алерты/дашборды/Sentry) | **35** | S35-001…S35-006 |
| H8 | Токены в localStorage, logout — no-op | — | Остаток `KI-027` → v0.7.0 (S51), §9 |
| H9 | Нет e-mail верификации и сброса пароля | 38 | S38-005 (решение; при отсутствии SMTP — `KI-035`) |
| H10 | Нет контент-безопасности LLM для детей / prompt injection | 38 | S38-006 (обзор, guardrails, `KI-036`) |

### 2.3. Medium (выборочно — те, что влияют на эксплуатацию)

| Находка | Куда | Задача |
|---------|------|--------|
| Один uvicorn-воркер | 35 | S35-001 (`UVICORN_WORKERS`, multiprocess-метрики) |
| Нет лимитов CPU/RAM и ротации логов | 35 | S35-005 |
| `UploadFile` без лимита, нет body-size/timeouts | 39 | S39-005 |
| Миграции при каждом старте | 36 | S36-004 |
| Контейнерный режим песочницы не собирается при деплое | 36 | S36-001 (образ `sandbox_runner` в GHCR) |
| README/ARCHITECTURE устарели | 40 | S40-005 |
| Наивные `datetime.utcnow()` (~1400) | — | §9, технический долг (v0.6.0) |
| Нет healthcheck в Dockerfile | — | Уже сделано (§1) |

### 2.4. Рекомендации аудита по размещению (для S36-003/006)

- **Пилот:** новый FirstVDS `94.250.252.142` (4 vCPU / 7,7 ГБ / 79 ГБ), рядом с
  workflow-builder. Минус: общий CPU и blast radius, **Caddy принадлежит
  workflow-builder** — порт 80/443 занят, наш vhost либо добавляется в его
  Caddy, либо поднимаем отдельный экземпляр на 8080/8443.
- **Публичный/школьный prod:** отдельный VPS (2–4 vCPU / 4–8 ГБ) — чище по
  изоляции и 152-ФЗ.
- **Не размещать:** `62.109.1.230` (VetAssistant + мониторинг),
  `89.108.70.62` (два прода), мини-ПК (только staging).
- **Ресурсы контейнеров (пилот):** app 2 ГБ, PostgreSQL 1 ГБ, Redis 128 МБ;
  диск 40 ГБ; GPU не нужен.

---

## 3. Карта KI → спринты

| KI | Severity | Статус | Спринт | Действие |
|----|----------|--------|--------|----------|
| `KI-023` | High | Open | 37 (старт — сразу) | Владелец: GitFlic-агент/токен или GitHub Pro; required checks; проверить красным MR. Fallback — ручной гейт по RULES §10 |
| `KI-027` | Accepted · Low | Accepted | — | Остаток после v0.5.0 (logout no-op, access не отзывает `token_version`, localStorage) — v0.6.0 S51; здесь не «дозакрываем» |
| `KI-032` | High | **новый** | 34 (S34-001) | `require_role` → `get_current_active_user`, регресс-тесты |
| `KI-033` | High | **новый** | 34 (S34-002) | `refresh_token` из query → тело; breaking-изменение, UPGRADE/CHANGELOG |
| `KI-034` | High | **новый** | 34 (S34-003) | `TRUSTED_PROXIES`, единый `client_ip()`, тесты подделки |
| `KI-035` | Med | кандидат | 38 (S38-005) | Верификация e-mail и сброс пароля, если SMTP/домен доступны в этапе; иначе — v0.6.0 |
| `KI-036` | Med | кандидат | 38 (S38-006) | Guardrails ответов LLM для детей, prompt injection |
| `KI-017` | Low | Resolved | 33, 37 | Риск окружения: PyPI/trivy DB/зеркала; wheelhouse и кэш |
| `KI-018` | Accepted · Low | Accepted | — | Не менять: `.format()` запрещён RestrictedPython; пересмотреть при обновлении библиотеки |

`KI-032`…`KI-034` заводятся в `docs/KNOWN_ISSUES.md` **первым шагом спринта 34**
(до правок), чтобы фикс и запись шли вместе. `KI-035`/`KI-036` — по итогам
решений S38-005/S38-006.

---

## 4. Обзор спринтов

| Спринт | Тема | Зависит от | Оценка | Статус | Ключевой результат |
|--------|------|------------|--------|--------|--------------------|
| 33 | Supply chain & repo hygiene | v0.5.0 | 3 дня (остаток ~2,5) | `[~]` | digest везде, сканы, SBOM, pre-commit, единые команды |
| 34 | **P0: Auth & Edge Hardening** | 33 (мягко) | 3 дня | `[x]` | `is_active` в ролях, refresh в теле, trusted proxy, лимиты, fail-fast `SECRET_KEY`, `DOCS_ENABLED` |
| 35 | Observability & Monitoring | 33, 34 | 3,5 дня | `[x]` | scrape, Sentry, Prometheus/Grafana/Loki, алерты, SLO, лимиты ресурсов |
| 36 | **Registry, Deploy, TLS & Backup/DR** | 35, 34 | 5,5 дня | `[x]` | GHCR + digest, Caddy/TLS, deploy/rollback, миграции job'ом, бэкапы+DR |
| 37 | CI Gates & GitFlic | 33; `KI-023` | 3 дня | `[~]` | preflight, coverage/parity-гейты; GitFlic-гейт готов, активация — владелец |
| 38 | Security & Privacy | 34, 36 | 3,5 дня | `[x]` | DPIA/ASVS L1, `*_FILE`, guardrails LLM, CSP/HSTS |
| 39 | Performance & Capacity | 35 | 3 дня | [x] | nightly health/tasks/submit, query-count тесты, кэш качества, лимиты/таймауты |
| 40 | DX & Docs | 33-39 | 2 дня | [x] | ADR-001…007, CONTRIBUTING/CODEOWNERS/шаблоны, env-drift, актуализация docs |
| 41 | Release v0.6.0 | 33–40 | 2,5 дня | `[ ]` | upgrade, тег, релизы, проверенный откат |

**Спринт 34 (P0) — Auth & Edge Hardening, выполнен 2026-11-11:**

| Задача | Что сделано | Статус |
|--------|-------------|--------|
| S34-001 | `require_role` → `get_current_active_user`; регресс-тесты teacher/admin (`KI-032`) | `[x]` |
| S34-002 | `refresh_token` в теле JSON; фронтенд + UPGRADE/CHANGELOG (`KI-033`) | `[x]` |
| S34-003 | `TRUSTED_PROXIES` + `client_ip`; rate limiter и audit (`KI-034`) | `[x]` |
| S34-004 | лимит `/auth/refresh` 30/мин; per-user `/code/execute` 30/мин | `[x]` |
| S34-005 | fail-fast при небезопасном `SECRET_KEY` (`DEBUG=false`) | `[x]` |
| S34-006 | `DOCS_ENABLED` (в prod — `false`) | `[x]` |
| S34-007 | `SECURITY.md`, `SPEC.md`, `RULES.md`, отчёты | `[x]` |

Отчёт: `docs/reports/sprint-34/SPRINT-34.md`. Тесты: полный backend-прогон
**754 passed, 1 skipped**; frontend `api.test.ts` — 6 passed.

**Логика порядка:**

- 33 закрывает фундамент supply chain; S33-001/002 уже сделаны — спринт
  короткий, его можно вести параллельно с 34.
- 34 — первым из нового: High-риски дают обход прав и защит *сейчас*, а не
  после деплоя. Дёшево (3 дня) и снимает главные претензии аудита.
- 35 до 36: деплой и алерты должны опираться на метрики (в т.ч.
  `backup_last_success_timestamp`), а лимиты ресурсов — на замеры.
- 36 — самый дорогой и самый блокирующий: без registry, TLS и бэкапов
  «устойчивого production» нет.
- 37 можно вести параллельно после 33: действие владельца по `KI-023` — длинный
  lead time, начинать сразу.
- 38 после 34/36: ASVS проверяет уже исправленные вещи и реальный TLS.
- 39 после 35: ёмкость меряется на подключённой наблюдаемости.
- 40 по мере готовности; 41 последним.

---

## 5. План по спринтам

### Спринт 33: Supply chain & Repo hygiene — `[~]`

**Цель:** воспроизводимые образы, управляемые зависимости и локальные хуки,
совпадающие с CI. Фундамент для 34–41.

**Зависит от:** v0.5.0 (сделано)  
**Оценка:** 3 дня (остаток ~2,5 дня)  
**Закрывает/снижает:** долг Dependabot, риск `KI-017`; готовит `KI-023`  
**Отчёт:** `docs/reports/sprint-33/SPRINT-33.md`

#### S33-001: Digest-пиннинг runtime-образов — `[x]`

- [x] `python:3.12-slim`, `node:22-alpine`, `nginx:1.27-alpine`,
      `pgvector/pgvector:pg17`, `redis:7-alpine` закреплены по digest в
      Dockerfile'ах и compose.
- [x] Guard `backend/scripts/check_image_pins.py` + 7 тестов; вызов в
      `scripts/ci/backend-lint.sh`.
- [x] Отчёт: `docs/reports/sprint-33/STEP-01_IMAGE_PINS_NONROOT.md`.

#### S33-002: Non-root backend — `[x]`

- [x] `USER app` (UID/GID 10001), `/app` read-only, запись только в `/tmp` и
      `PROMETHEUS_MULTIPROC_DIR`; `PYTHONDONTWRITEBYTECODE=1`.
- [x] Проверены `id`, запись в `/tmp`, `[ -w /app ]` → false, `alembic check`,
      `/health/ready`, полный `pytest` в образе.

#### S33-003: CI-образы, `hadolint` и `trivy` — `[ ]`

- [ ] Закрепить по digest все образы в CI: `python:3.12-slim`, `node:22-alpine`,
      `pgvector/pgvector:pg17`, `redis:7-alpine`, `gitleaks` в
      `.github/workflows/ci.yml`, `ci-selfhosted.yml`, `release.yml`,
      `gitflic-ci.yaml`, `ci/gitflic-pilot.yaml`, `scripts/ci/build-wheelhouse.ps1`;
      убрать дубли пилота.
- [ ] Политика для GitHub Actions: полный commit SHA (предпочтительно) или
      major-тег + Dependabot; обоснование — в `docs/CI.md`.
- [ ] Расширить `backend/scripts/check_image_pins.py` на workflow/CI-YAML и
      скрипты; тесты на новые файлы; guard остаётся в lint.
- [ ] `.hadolint.yaml` (игноры только с обоснованием) и `trivy image
      --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1` для backend,
      frontend и **sandbox-runner** (аудит: образ песочницы не собирается при
      деплое — входит в S36-001); отчёты — артефактами.
- [ ] `scripts/ci/supply-chain.ps1` + `.sh`, job в GitHub и GitFlic;
      локальная команда `make supply-chain`.
- [ ] **Зависит от:** S33-001 · **Оценка:** 6 ч

#### S33-004: SBOM CycloneDX — `[ ]`

- [ ] CycloneDX SBOM для трёх образов через `trivy`
      (`artifacts/sbom/*.cdx.json`) + `SHA256SUMS`.
- [ ] Прикреплять SBOM к GitHub Release и GitFlic Release; хранить артефакты
      не менее 90 дней.
- [ ] `scripts/ci/verify_sbom.py`: непустой список компонентов, совпадение
      base-digest, отсутствие дублей.
- [ ] **Зависит от:** S33-003 · **Оценка:** 3 ч

#### S33-005: Dependabot — политика, долг и repo hygiene — `[ ]`

- [ ] Инвентаризировать открытые PR: смержить зелёные minor/patch, закрыть
      устаревшие с комментарием, major — отдельно с причиной; таблица решений —
      в отчёте спринта.
- [ ] Обновить `.github/dependabot.yml`: `docker`-экосистема, группы для
      actions, лимиты, cooldown; major — только вручную.
- [ ] Авто-мерж остаётся заблокированным `KI-023`; ручной SLA (триаж раз в
      неделю, мерж только после зелёного CI) — в `docs/CI.md`.
- [ ] Repo hygiene: удалить смерженные ветки, проверить теги, `.gitignore`,
      `.gitattributes`, отсутствие крупных/секретных файлов.
- [ ] **Зависит от:** S33-003 · **Оценка:** 3 ч

#### S33-006: Pre-commit — `[ ]`

- [ ] `.pre-commit-config.yaml`: trailing-whitespace, end-of-file-fixer,
      check-yaml, check-merge-conflict, check-added-large-files; `ruff`;
      `gitleaks`; локальные хуки `check-i18n.mjs`, `check_version.py`,
      `check_image_pins.py`.
- [ ] `pre-commit run --all-files` зелёный; тот же набор в CI, чтобы локальные
      и CI-гейты не расходились.
- [ ] Инструкция для Windows/macOS/Linux — `CONTRIBUTING.md` (S40), краткая
      версия — `docs/GETTING_STARTED.md` и `RULES.md`.
- [ ] **Зависит от:** S33-003, S33-005 · **Оценка:** 3 ч

#### S33-007: Единые команды (`Makefile` + PowerShell) — `[ ]`

- [ ] `Makefile`: `help`, `lint`, `test`, `test-fast`, `test-image`, `e2e`,
      `frontend`, `docker`, `supply-chain`, `release-check`; делегируют в
      `scripts/ci/*`.
- [ ] `scripts/tasks.ps1` с теми же целями (PowerShell 7); `Makefile` — тонкая
      обёртка для Git Bash/Linux/CI.
- [ ] `make release-check` = все гейты без создания релиза; `make test-image` =
      полный `pytest` в собранном образе.
- [ ] Таблица команд в `docs/GETTING_STARTED.md`; ссылка из `docs/README.md`.
- [ ] **Зависит от:** S33-003 · **Оценка:** 4 ч

#### S33-008: Документация и закрытие спринта — `[ ]`

- [ ] `RULES.md` §11.27: CI-образы, `trivy`/`hadolint`, SBOM, pre-commit.
- [ ] `docs/CI.md`: новые job'ы, артефакты, политика Actions/Dependabot.
- [ ] `CHANGELOG.md` (`[Unreleased]`), `RELEASES.md`, отчёт `SPRINT-33.md`.
- [ ] **Зависит от:** S33-003…S33-007 · **Оценка:** 2 ч

**DoD:** все `FROM`/`image:` и CI-образы закреплены; guard покрывает новые
файлы; `hadolint`/`trivy` — 0 HIGH/CRITICAL (или принято с expiry); SBOM
генерируется; `pre-commit run --all-files` и `make lint/test` зелёные;
Dependabot-долг разобран; спринт-отчёт заполнен.

---

### Спринт 34: P0 — Auth & Edge Hardening — `[x]` (завершён 2026-11-11)

**Цель:** закрыть High-риски аудита, которые дают обход авторизации и лимитов
прямо сейчас. Это первый спринт нового этапа: он дешёвый, не зависит от
инфраструктуры и снимает главные претензии аудита к безопасности.

**Зависит от:** v0.5.0; мягко — спринт 33 (guard образов не мешает)  
**Оценка:** 3 дня (факт — 1 день)  
**Закрывает:** `KI-032`, `KI-033`, `KI-034`; сужает поверхность атаки до
старта деплоя  
**Отчёт:** `docs/reports/sprint-34/SPRINT-34.md`

> **Нулевой шаг выполнен:** `KI-032`…`KI-035` заведены в
> `docs/KNOWN_ISSUES.md` до правок; `KI-032`…`KI-034` закрыты в этом спринте,
> `KI-035` отложен на v0.7.0.

#### S34-001: `require_role` и `is_active` (`KI-032`) — `[x]`

- [x] `require_role` зависит от `get_current_active_user`; деактивированный
      teacher/admin получает **401** («Аккаунт удалён») сразу, не дожидаясь
      истечения access-токена.
- [x] Аудит `Depends(get_current_user)`: намеренно оставлены `logout` и путь
      refresh/login (проверка активности там своя); `get_current_active_user`
      используется в защищённых маршрутах и RBAC.
- [x] Регресс-тесты в `tests/test_auth.py`: активный teacher/admin — 200;
      деактивированный teacher/admin — 401. Аудит пришёл к выводу, что
      `401` корректнее `403` (не раскрываем существование аккаунта).
- [x] **Зависит от:** — · **Оценка:** 3 ч (факт ~2 ч)

#### S34-002: `refresh_token` из query string в тело (`KI-033`) — `[x]`

- [x] `POST /api/v1/auth/refresh` принимает JSON-тело
      `{"refresh_token": "..."}` (`RefreshTokenRequest`, Pydantic);
      query-вариант удалён — breaking-изменение.
- [x] Обновлены фронтенд (`src/lib/api.ts`, `refreshAccessToken`) и все тесты,
      где refresh вызывался с `params=`: `test_auth.py`, `test_sessions.py`,
      `test_password_change.py`, `test_profile_selfservice.py`.
- [x] Контрактный снапшот проходит (изменение аддитивное — тело вместо query);
      `CHANGELOG` — раздел Breaking; `docs/UPGRADE.md` §0.5 — миграция клиентов.
- [x] Ответ `/refresh` отдаётся с `Cache-Control: no-store`; токен в теле не
      попадает в access-логи (query больше не используется), тест проверяет
      заголовок.
- [x] **Зависит от:** — · **Оценка:** 4 ч (факт ~3 ч)

#### S34-003: Trusted proxy для `X-Forwarded-For` (`KI-034`) — `[x]`

- [x] `Settings.trusted_proxies` (`TRUSTED_PROXIES`, IP/CIDR, по умолчанию
      пусто = заголовку не доверяем) + `app/core/ip_utils.py::client_ip`:
      XFF разбирается справа налево, доверенные хопы пропускаются; при
      отсутствии доверия — `request.client.host`. (Имя модуля — `ip_utils.py`.)
- [x] Дублирующиеся разборы в `rate_limiter` и `audit_service` заменены общим
      helper; поведение одинаково в лимитах и audit-логе.
- [x] Требование к edge зафиксировано для S36-003
      (`proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for` /
      `trusted_proxies` в Caddy); в prod-compose задан `TRUSTED_PROXIES=127.0.0.1`.
- [x] Тесты: подделка XFF не расширяет лимит (в т.ч. за доверенным прокси);
      реальный IP за trusted proxy определяется; пустой/битый заголовок не
      ломает запрос; CIDR.
- [x] **Зависит от:** — · **Оценка:** 5 ч (факт ~4 ч)

#### S34-004: Лимиты на `/auth/refresh` и `/code/execute` — `[x]`

- [x] Отдельный лимит refresh — на IP (`refresh:<ip>`, 30/мин), независимый от
      общего и login-лимита. `/code/execute` — per-user ключ
      (`code_execute:<id>`, 30/мин), а не общий IP-лимит 300/мин.
- [x] Метрика `rate_limit_blocked_total{scope}` вынесена в спринт 35
      (наблюдаемость): здесь поведение покрыто тестами.
- [x] Тесты: 429 при превышении; лимит одного пользователя не блокирует
      другого; NAT/общий IP не страдает от per-user лимита; fail-open.
- [x] **Зависит от:** S34-003 · **Оценка:** 3 ч (факт ~3 ч)

#### S34-005: Fail-fast `SECRET_KEY` в production — `[x]`

- [x] `validate_security_settings()` в `lifespan`: `DEBUG=false` и
      (`SECRET_KEY == DEFAULT_SECRET_KEY` или длина < 32) →
      `InsecureSettingsError(RuntimeError)`, старт прерывается; в dev проверка
      пропускается.
- [x] Prod compose уже требует `SECRET_KEY`/`POSTGRES_PASSWORD` через `${VAR:?}`;
      зафиксировано в `SECURITY.md`/`RULES.md`.
- [x] Тесты: `DEBUG=false` + дефолтный/короткий ключ → исключение; валидный
      ключ и `DEBUG=true` — старт ок.
- [x] **Зависит от:** — · **Оценка:** 2 ч (факт ~1 ч)

#### S34-006: Публичный Swagger/OpenAPI в prod — `[x]`

- [x] `DOCS_ENABLED` (default `true`; в `docker-compose.prod.yml` — `false`):
      при `false` — `docs_url=None`, `redoc_url=None`, `openapi_url=None`;
      контрактные тесты работают через `app.openapi()` независимо от флага.
- [x] Тест: при `false` `/api/docs`, `/api/redoc`, `/api/openapi.json` → 404;
      `/health/*` и `/metrics` не затронуты.
- [x] **Зависит от:** — · **Оценка:** 2 ч (факт ~1 ч)

#### S34-007: Документация и закрытие спринта — `[x]`

- [x] `KNOWN_ISSUES.md` (`KI-032`…`KI-034` → Closed с доказательствами;
      `KI-035` → Open, v0.7.0), `RULES.md` §11.49 «Клиентский IP, доверенные
      прокси и лимиты», `SECURITY.md`, `SPEC.md` §3.12.
- [x] `CHANGELOG.md` (`[0.6.0]`), `RELEASES.md`, `UPGRADE.md` §0.5,
      отчёты `docs/reports/sprint-34/`.
- [x] **Зависит от:** S34-001…S34-006 · **Оценка:** 2 ч (факт ~2 ч)

**DoD:** деактивированный teacher/admin получает **401** независимо от срока
жизни access-токена; refresh работает только из тела (`Cache-Control:
no-store`), токен не попадает в логи; подделка `X-Forwarded-For` не расширяет
лимит; `/auth/refresh` и `/code/execute` имеют собственные лимиты; prod не
стартует с дефолтным `SECRET_KEY`; `/api/docs` в prod закрыт; все тесты и гейты
зелёные.

---

### Спринт 35: Observability & Monitoring — `[x]` (завершён 2026-11-12)

**Цель:** метрики, ошибки и трейсы реально собираются; алерты и дашборды лежат
в репозитории и поднимаются одной командой; ресурсы ограничены, логи не
съедают диск.

**Зависит от:** спринты 33, 34 (метрика `rate_limit_blocked_total`)  
**Оценка:** 3,5 дня (факт — 1 день)  
**Отчёт:** `docs/reports/sprint-35/SPRINT-35.md`

#### S35-001: Scrape `/metrics` и multiprocess-режим — `[x]`

- [x] `docker-compose.monitoring.yml` (профиль `monitoring`): Prometheus
      scrapes `backend:8000/metrics` каждые 15 с; `/metrics` **не** публикуется
      наружу (nginx отдаёт 404, порт backend не публикуется — сохранено).
- [x] `UVICORN_WORKERS=2` (prod), `PROMETHEUS_MULTIPROC_DIR` (tmpfs `1777`);
      каталог чистит entrypoint; `METRICS_ENABLED=true` в prod.
- [x] Тесты: `tests/test_metrics_export.py` — два процесса-«воркера»
      агрегируются в счётчиках/гистограммах; `/metrics` отсутствует при
      `METRICS_ENABLED=false`; smoke-скрипт
      `scripts/monitoring/check_metrics.py --expect-workers 2`.
- [x] **Зависит от:** — · **Оценка:** 5 ч (факт ~4 ч)

#### S35-002: Sentry (backend + frontend) — `[x]`

- [x] Backend: `sentry-sdk[fastapi]==2.74.0`; `SENTRY_DSN`,
      `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE`, `SENTRY_RELEASE`;
      `send_default_pii=False`, `max_request_body_size="never"`, `before_send`
      вычищает email, IP, токены, код и промпты.
- [x] Frontend: `@sentry/react@11.12.0`, runtime-конфиг `/config.js`
      (entrypoint контейнера из ENV), source maps — задача релиза; release =
      версия + git-sha через `APP_RELEASE`.
- [x] No-op без DSN (`tests/test_sentry.py`, `src/test/sentry.test.ts`);
      ошибка Sentry не роняет запрос/старт.
- [x] CSP (`connect-src` для `*.sentry.io`), `docs/PRIVACY.md` §7.
- [x] **Зависит от:** — · **Оценка:** 5 ч (факт ~4 ч)

#### S35-003: Prometheus-правила и алерты как код — `[x]`

- [x] `deploy/monitoring/prometheus/{prometheus.yml,rules/alerts.yml,rules/recording.yml}`;
      `promtool check config` и `check rules` — локальные скрипты
      `scripts/monitoring/validate_prometheus.{sh,ps1}` и CI job
      **Monitoring config** (`ci.yml`, `ci-selfhosted.yml`).
- [x] Алерты: 5xx rate > 5%, p95 API, LLM error/latency, fallback, sandbox
      timeouts/errors, DB/Redis down, pool saturation, target down, rate-limit
      spike, retention stale, `BackupStale` (метрика — S36);
      `severity`, `runbook_url`, `summary`.
- [x] Добавлены метрики `db_up`, `redis_up`, `rate_limit_blocked_total`,
      `scheduler_last_success_timestamp` (S35-003).
- [x] **Зависит от:** S35-001 · **Оценка:** 4 ч (факт ~4 ч)

#### S35-004: Grafana-дашборды как код — `[x]`

- [x] `deploy/monitoring/grafana/provisioning/{datasources,dashboards}`;
      дашборд `ai-teacher-overview.json`: API/HTTP, LLM (латентность, токены,
      fallback), пул БД, песочница, rate limit.
- [x] Переменные `route`, `provider`; валидация JSON —
      `scripts/monitoring/validate_dashboards.py` и
      `tests/test_monitoring_config.py`.
- [x] Smoke: provisioning поднимается вместе с профилем `monitoring`
      (команды и доступ — `docs/MONITORING.md`).
- [x] **Зависит от:** S35-003 · **Оценка:** 4 ч (факт ~3 ч)

#### S35-005: Лимиты CPU/RAM, логи и ротация — `[x]`

- [x] `mem_limit`/`cpus` для всех сервисов: backend 2 ГБ/2.0, PostgreSQL
      1 ГБ/1.0, Redis 128 МБ/0.5, frontend 256 МБ/0.5, Prometheus 512 МБ,
      Grafana 256 МБ, Loki 256 МБ, Promtail 128 МБ.
- [x] Docker logging `json-file`, `max-size: 10m`, `max-file: "3"` для всех
      сервисов; политика PII — `RULES.md` §11.50.
- [x] Профиль `monitoring` опционален: prod работает без него; замеры
      `docker stats` — в отчёте спринта.
- [x] **Зависит от:** S35-001 · **Оценка:** 3 ч (факт ~2 ч)

#### S35-006: SLO и бюджеты ошибок — `[x]`

- [x] `docs/SLO.md`: доступность ≥ 99%/30 дней, ошибки < 1%, health p95
      < 100 мс, API p95 ≤ 500 мс, submit p95 ≤ 2 с, успешность LLM ≥ 99%;
      error budget (≈7 ч 12 мин), burn-rate и правила расходования.
- [x] Связь «алерт → SLO → runbook»: `docs/SLO.md` §4 и
      `docs/MONITORING.md` §6.
- [x] **Зависит от:** S35-003 · **Оценка:** 3 ч (факт ~2 ч)

#### S35-007: Документация и закрытие спринта — `[x]`

- [x] `docs/MONITORING.md`: архитектура, команды, UI/порты, каталог алертов,
      Sentry/PII, лимиты и логи, troubleshooting, ограничения одного узла.
- [x] `CHANGELOG.md`, `RELEASES.md`, отчёт `SPRINT-35.md`.
- [x] **Зависит от:** S35-001…S35-006 · **Оценка:** 2 ч (факт ~2 ч)

**DoD:** `docker compose -f docker-compose.prod.yml -f docker-compose.monitoring.yml
--profile monitoring up -d` поднимает Prometheus, Grafana и Loki; все targets
`UP`; правила и дашборды валидируются `promtool`; Sentry ловит тестовую ошибку
и не отправляет PII; SLO-документ есть; лимиты CPU/RAM и ротация логов
включены; прод работает без профиля `monitoring`.

---

### Спринт 36: Registry, Deploy, TLS & Backup/DR — `[x]` (завершён 2026-11-12)

**Цель:** воспроизводимый артефакт в registry, закрытый TLS-периметр,
деплой/откат одной командой, автоматические бэкапы с off-site и проверенным
восстановлением. Самый дорогой спринт этапа — он снимает blocker'ы B2–B4.

**Зависит от:** спринты 34 (trusted proxy), 35 (метрики бэкапов, алерты)  
**Оценка:** 5,5 дня  
**Закрывает:** blocker'ы B2–B4 аудита  
**Отчёт:** `docs/reports/sprint-36/SPRINT-36.md`

#### S36-001: GHCR: сборка и публикация образов — `[x]`

- [x] Workflow `docker-publish.yml`: `docker/build-push-action` для `backend`,
      `frontend`, `sandbox-runner` → `ghcr.io/<owner>/ai-teacher-*`.
- [x] Теги `:<tag>` + `:sha-<short>`; `latest` не публикуется. `permissions:
      packages: write`; кэш `type=gha`; SBOM/provenance.
- [x] `sandbox_runner` собирается в CI (контекст `backend/`).
- [x] Документация: `docs/RUNBOOK.md`/`docs/GETTING_STARTED.md` §7 — логин в
      GHCR, pin digest, деплой. (Отдельный `DEPLOY.md` не заводился.)
- [x] **Зависит от:** S33-003 · **Оценка:** 5 ч (факт ~3 ч)

#### S36-002: Digest-пиннинг релизных образов — `[x]`

- [x] Prod-compose использует `ghcr.io/<owner>/ai-teacher-*@sha256:...` через
      `BACKEND_IMAGE`/`FRONTEND_IMAGE`/`SANDBOX_IMAGE`; fallback — `IMAGE_TAG`.
- [x] `scripts/pin_images.sh`: digest из `docker buildx imagetools inspect`
      (fallback `docker pull` + `RepoDigests`), запись в `.env.prod`;
      `--dry-run` и `--digest` для офлайн-проверки.
- [x] `check_image_pins.py` обновлён: ENV/алиасы разрешены, `latest` запрещён,
      monitoring-compose включён.
- [x] **Зависит от:** S36-001 · **Оценка:** 4 ч (факт ~3 ч)

#### S36-003: Caddy, TLS и периметр — `[x]`

- [x] `deploy/caddy/Caddyfile`: ACME/TLS, `reverse_proxy frontend:80`,
      `/api/*` → `backend:8000` (WebSocket автоматически), HSTS, JSON-логи.
- [x] Frontend без `ports`, только `expose: 80`; единственный публичный
      слушатель — Caddy (80/443; на пилоте 8080/8443 через ENV).
- [x] `TRUSTED_PROXIES=10.77.0.0/16` совпадает с Docker-подсетью edge;
      backend принимает XFF только от Caddy.
- [x] Проверки: `caddy validate` — `Valid configuration`; `compose config`.
      `testssl.sh`/SSL Labs и реальный ACME — на пилоте (нет домена в CI).
- [x] Healthcheck Caddy-контейнера (`caddy validate`).
- [x] **Зависит от:** S34-003 · **Оценка:** 5 ч (факт ~3 ч)

#### S36-004: Миграции отдельным job'ом — `[x]`

- [x] One-shot сервис `migrate` (profile `tools`), backend стартует с
      `SKIP_MIGRATIONS=true`; deploy: `migrate` → `up` → health.
- [x] Ошибка миграции останавливает deploy (set -e / on_error); `alembic check`
      остаётся гейтом (существующие тесты миграций).
- [x] **Зависит от:** S36-001 · **Оценка:** 3 ч (факт ~2 ч)

#### S36-005: `deploy` и `rollback` — `[x]`

- [x] `scripts/deploy.sh`: preflight (`compose config`, ENV, секреты),
      бэкап, pull по тегу/digest, migrate, `up -d --no-deps --remove-orphans`,
      health-gate `/health/ready`; флаги `--dry-run`, `--no-backup`,
      `--no-pull`, `--skip-migrations`.
- [x] `.deploy-state`/`.last_deploy` (gitignored): при ошибке — автоматический
      `rollback.sh` на предыдущее состояние и повторный health-gate.
- [x] `scripts/rollback.sh`: `.last_deploy`/`--to`, pull, up, health, обновление
      state. Полный откат на стенде не выполнялся (нет образов GHCR);
      проверены `--dry-run` и конфигурация.
- [x] **Зависит от:** S36-002, S36-004 · **Оценка:** 8 ч (факт ~4 ч)

#### S36-006: Бэкапы: systemd, S3, фикс имени контейнера — `[x]`

- [x] `scripts/backup.sh`: контейнер через `docker compose ps -q postgres`,
      fallback `POSTGRES_CONTAINER`; ошибка, если не найден.
- [x] S3 (Selectel) при `AWS_ACCESS_KEY_ID` + `S3_BUCKET` (aws-cli/s3cmd,
      `S3_ENDPOINT_URL`), `age`-шифрование при `AGE_RECIPIENT`, sha256,
      локальный retention, `--dry-run`/`--no-s3`.
- [x] systemd `ai-teacher-backup.service` + `.timer` (03:00, `Persistent=true`,
      `EnvironmentFile`); `OnFailure=` не настраивался — алерт `BackupStale`.
- [x] Метрика `backup_last_success_timestamp` через node-exporter textfile.
- [x] Проверено: локальный бэкап + `pg_restore -l`; S3/age не запускались
      (нет ключей/age).
- [x] **Зависит от:** S35-003 · **Оценка:** 6 ч (факт ~4 ч)

#### S36-007: Автоматический restore drill — `[x]`

- [x] `scripts/restore_drill.sh`: последний бэкап → scratch-БД → `pg_restore`
      → проверка `alembic_version`/`users`/таблиц → удаление scratch;
      `--keep`, `--dry-run`; лог в `backups/dr-reports/`.
- [x] Реальный прогон: 17 таблиц, users=32, alembic OK, scratch удалена.
      Ночной таймер не заводился — рекомендация в отчёте.
- [x] **Зависит от:** S36-006 · **Оценка:** 4 ч (факт ~2 ч)

#### S36-008: Runbook инцидентов — `[x]`

- [x] `docs/RUNBOOK.md`: деплой/откат, БД, Redis, backend, Caddy/TLS, диск,
      бэкап/restore/DR, секреты, алерты, эскалация, постмортем.
- [x] Ссылки на MONITORING/SLO/скрипты; обновлён DESIGN §10.
- [x] **Зависит от:** S35-003, S36-002…S36-007 · **Оценка:** 4 ч (факт ~2 ч)

#### S36-009: Документация и закрытие спринта — `[x]`

- [x] `UPGRADE.md` §0.7.1/§0.8, `ARCHITECTURE.md` §9.3/§10,
      `GETTING_STARTED.md` §7–8, `SECURITY.md`, `CHANGELOG.md`,
      `RELEASES.md`, отчёт `SPRINT-36.md`.
- [x] **Зависит от:** S36-001…S36-008 · **Оценка:** 2 ч (факт ~2 ч)

**DoD:** на сервере нет сборки из исходников — только pull по digest; сайт
доступен по HTTPS-домену, `:3000` не опубликован, HSTS только по TLS; откат на
предыдущее состояние — одна команда (проверен `--dry-run`, полный — на стенде);
миграции отдельным job'ом; бэкап поддерживает S3/age по systemd-таймеру, алерт
`BackupStale` связан с реальной метрикой node-exporter; restore drill зелёный
(реальный прогон на dev-БД); runbook покрывает ключевые инциденты.

---

### Спринт 37: CI Gates & GitFlic — `[x]` (инженерия завершена 2026-11-12; активация GitFlic-гейта — владелец)

**Цель:** красный PR физически не мержится; все гейты воспроизводимы локально;
паритет GitHub ↔ GitFlic.

**Зависит от:** спринт 33; действие владельца по `KI-023`  
**Оценка:** 3 дня (часть может быть `Blocked`)  
**Закрывает:** `KI-023` — при наличии доступа владельца  
**Отчёт:** `docs/reports/sprint-37/SPRINT-37.md`

> **Контекст:** зависший CI из-за офлайн-раннера не считается блокером этапа
> (решение владельца). Но required checks без живого раннера бессмысленны,
> поэтому S37-001 и S37-004 включают health-check раннера и таймауты.

#### S37-001: GitFlic-агент и required checks (`KI-023`) — `[~]`

- [ ] Владелец: зарегистрировать PowerShell/Docker-агент, выдать токен, включить
      MR-пайплайн и «проверять статус последнего конвейера». (В S37 доступа не
      было; подготовлены `scripts/ci/gitflic-gate.ps1` и `docs/CI.md` §14.2.)
- [ ] Проверить на тестовом MR, что красный конвейер блокирует merge; если нет —
      gate через webhook/скрипт, решение — в `docs/CI.md`.
- [x] Если доступа нет к началу спринта: `KI-023` остаётся `In Progress`,
      фиксируем fallback (ручной гейт + `gates.ps1|sh`), не имитируем гейт.
- [x] **Зависит от:** доступ владельца · **Оценка:** 6 ч + ожидание

#### S37-002: Паритет GitHub ↔ GitFlic — `[x]`

- [x] Сопоставить job'ы (lint, test, frontend, security, e2e, docker,
      supply-chain, promtool) с этапами GitFlic: одинаковые команды, образы,
      кэш, артефакты.
- [x] `gitflic-ci.yaml` — digest-пиннинг, path-фильтры, `needs`, таймауты;
      убрать расхождения и мёртвые job'ы.
- [x] **Зависит от:** S33-003 · **Оценка:** 5 ч

#### S37-003: Coverage-гейт — `[x]`

- [x] Backend: `pytest --cov=app --cov-report=xml --cov-fail-under=70` в CI;
      отчёт — артефакт, порог не снижать без записи в KI.
- [x] Frontend: thresholds в конфиге Vitest (lines/functions/branches/
      statements), отчёт в CI.
- [x] **Зависит от:** S37-002 · **Оценка:** 3 ч

#### S37-004: Скорость и надёжность CI — `[x]`

- [x] `timeout-minutes`, `concurrency: cancel-in-progress`, кэш pip/pnpm,
      Docker layer cache, разумный retention артефактов.
- [x] Preflight-проверка доступности self-hosted раннера (быстрый ping-job) и
      fail-fast по таймауту вместо «висящего» прогона; политика ручного
      перезапуска при офлайне — в `docs/CI.md`.
- [x] Цель: lint+test+frontend < 15 мин; локальный `gates --fast` укладывается
      (~1,5 мин), полный прогон зависит от БД/e2e; точный замер на runner'е —
      после активации (см. отчёт).
- [x] **Зависит от:** S37-002 · **Оценка:** 3 ч

#### S37-005: Единый локальный прогон гейтов — `[x]`

- [x] `scripts/ci/gates.ps1` + `gates.sh`: `--fast` (lint/type/unit), `--full`
      (+ e2e, docker, supply-chain, coverage, promtool), `--ci` (без
      интерактива), JSON-сводка; коды выхода.
- [x] `make release-check` вызывает тот же скрипт; список гейтов совпадает с CI
      (проверка тестом/скриптом).
- [x] **Зависит от:** S37-002 · **Оценка:** 4 ч

#### S37-006: Документация и закрытие спринта — `[x]`

- [x] `RULES.md` §10, `docs/CI.md`, `KNOWN_ISSUES.md` (`KI-023`),
      `CHANGELOG.md`, `RELEASES.md`, отчёт `SPRINT-37.md`.
- [x] **Зависит от:** S37-001…S37-005 · **Оценка:** 2 ч

**DoD:** preflight стоит первым шагом во всех self-hosted job'ах и GitFlic;
coverage-гейт активен (backend 70%, frontend `test:coverage`); паритет
Lint/Test/Frontend/Security проверяется `scripts/ci/check_ci_parity.py`;
локальный `gates --fast/--full` воспроизводит CI; GitFlic-гейт подготовлен
(скрипт + инструкция), но его активация требует доступа владельца — `KI-023`
остаётся `In Progress` до красного тестового MR.

---

### Спринт 38: Security & Privacy — `[x]` (завершён 2026-11-12)

**Цель:** подтвердить ASVS L1, убрать секреты из конфигов, принять явные
решения по e-mail-восстановлению и безопасности ответов LLM для детей.

**Зависит от:** спринты 34, 36  
**Оценка:** 3,5 дня  
**Отчёт:** `docs/reports/sprint-38/SPRINT-38.md`

> Задачи, закрытые в спринте 34 (is_active, refresh, XFF, `SECRET_KEY`,
> Swagger), здесь только **проверяются в ASVS** — второй раз не фиксятся.

#### S38-001: Инвентаризация PII и DPIA — `[x]`

- [x] Инвентаризация: email, имя, чаты, код, эмбеддинги, audit IP; где
      хранится, срок, кто обработчик (DeepSeek/LLM), трансграничная передача;
      что уходит в Sentry (S35-002).
- [x] `docs/DPIA.md`: цели, правовое основание, права субъекта, меры защиты,
      остаточные риски; приложение-ссылка из `docs/PRIVACY.md`.
- [x] **Зависит от:** S35-002 · **Оценка:** 4 ч

#### S38-002: Секреты вне конфигов — `[x]`

- [x] Docker secrets / `*_FILE` для `SECRET_KEY`, `DEEPSEEK_API_KEY`,
      `POSTGRES_PASSWORD`, SMTP/S3-credentials; приоритет file над ENV.
- [x] `docker-compose.prod.yml`: secrets вместо открытых значений; процедура
      ротации; стартовая валидация небезопасных значений.
- [x] Тесты на `_FILE` и приоритет; `gitleaks` остаётся гейтом.
- [x] **Зависит от:** S34-005 · **Оценка:** 6 ч

#### S38-003: OWASP ASVS L1 — `[x]`

- [x] `docs/ASVS_L1.md`: чек-лист с доказательствами (auth, session, access
      control, validation, crypto, errors/logging, data protection,
      configuration); ссылки на тесты и коммиты, включая S34-001…S34-006.
- [x] Открытые пункты — в `KNOWN_ISSUES.md` с severity и планом; без «галочек»
      без доказательств.
- [x] **Зависит от:** S38-001, S38-002, S36-003 · **Оценка:** 5 ч

#### S38-004: CSP/security headers после TLS и мониторинга — `[x]`

- [x] Проверить CSP/заголовки после появления Caddy, Sentry и WS; добавить
      `Cross-Origin-Opener-Policy`/`Cross-Origin-Resource-Policy`, если не ломают
      Monaco и API.
- [x] HSTS — только при реальном TLS (S36-003); убрать дубль из nginx;
      проверка `curl -I` в smoke.
- [x] **Зависит от:** S36-003 · **Оценка:** 3 ч

#### S38-005: Верификация e-mail и сброс пароля — решение — `[x]`

- [x] Аудит H9: восстановление аккаунта сейчас невозможно (только смена пароля
      изнутри). Оценить стоимость: SMTP-провайдер/домен, шаблоны писем,
      rate-limit на отправку, токены с TTL, анти-энумерация.
- [x] Если SMTP и домен доступны в этапе — минимальная реализация:
      `POST /auth/password/forgot` (всегда 202), `POST /auth/password/reset`,
      `POST /auth/email/verify`; иначе — `KI-035` (Med) и перенос в v0.6.0.
- [x] Решение и обоснование — ADR (S40-001), не «устное».
- [x] **Зависит от:** S36-003 · **Оценка:** 4 ч (без реализации) / +8 ч при реализации

#### S38-006: Безопасность ответов LLM для детей — обзор — `[x]`

- [x] Аудит H10: prompt injection через код ученика/задания, отсутствие
      guardrails на ответы (кроме эвристики «не давать готовый код»), поведение
      при утечке системного промпта.
- [x] Сценарии атак покрыты unit-тестами `tests/test_guardrails.py` (21):
      injection EN/RU, «покажи промпт», смена роли, токсичность,
      самоповреждение, ложные срабатывания на учебных вопросах. Живой прогон
      DeepSeek не выполнялся (нет ключа) — отмечено в `LLM_EVAL.md` §8.
- [x] Найденное критичное закрыто в спринте: защитные инструкции во всех
      промптах + фильтр входа до сохранения/LLM; полная модерация ответов
      вынесена в `KI-036` (Med).
- [x] **Зависит от:** — · **Оценка:** 4 ч (факт ~4 ч)

#### S38-007: Документация и закрытие спринта — `[x]`

- [x] `SECURITY.md`, `PRIVACY.md`, `RULES.md`, `KNOWN_ISSUES.md`,
      `CHANGELOG.md`, `RELEASES.md`, отчёт `SPRINT-38.md`.
- [x] **Зависит от:** S38-001…S38-006 · **Оценка:** 2 ч

**DoD:** ASVS L1 пройден без открытых High в приложении (`KI-023` — процессный);
секреты можно передавать через `*_FILE`/Docker secrets; `KI-035` и `KI-036`
заведены; CSP/HSTS/заголовки валидированы (`caddy validate`, тест конфигурации;
реальный TLS/ACME — на пилоте); DPIA и инвентаризация PII готовы.

---

### Спринт 39: Performance & Capacity — `[x]` (завершён 2026-11-12)

**Цель:** известна ёмкость узла, регресс ловится nightly, входные лимиты не
позволяют одному запросу съесть память или соединение.

**Зависит от:** спринт 35  
**Оценка:** 3 дня  
**Отчёт:** `docs/reports/sprint-39/SPRINT-39.md`

#### S39-001: Нагрузочный тест в nightly — `[x]`

- [x] `load_test.py`: сценарии health (20 RPS), tasks (10 RPS), submit
      (5 RPS), бюджеты p95/error rate; baseline `docs/reports/perf/baseline.json`
      (статус `pending_runner`, реальный замер — после первого nightly).
- [x] Nightly workflow (GitHub, self-hosted) + `compare_perf.py` (регресс >20%);
      артефакт `load-test-night.json`. GitFlic — ручной запуск (расписаний в
      YAML нет), паритет базовых гейтов сохранён.
- [x] **Зависит от:** S35-001 · **Оценка:** 6 ч (факт ~3 ч)

#### S39-002: N+1 и индексы — `[x]`

- [x] Query-count регрессии (`tests/test_query_counts.py`) для `/admin/users`,
      `/admin/audit`, `/admin/tasks/review`, `/me/notifications`: число SELECT
      не растёт с числом строк. `pg_stat_statements`/`EXPLAIN` — рекомендация
      на пилот, отдельного расширения в compose не включали.
- [x] Индексы проверены по коду; подтверждённой необходимости в новой
      миграции нет (существующие покрывают фильтры/сортировки).
- [x] **Зависит от:** S35-001 · **Оценка:** 6 ч (факт ~3 ч)

#### S39-003: Кэш: hit-rate и инвалидация — `[x]`

- [x] Метрики `cache_hits_total`/`cache_misses_total` и hit-rate в
      `/admin/analytics` уже есть (S19/S35); отдельный порог/алерт не
      добавляли — наблюдаем по дашборду.
- [x] Кэш сводки качества (`cache:admin:quality`, TTL 60 c) с инвалидацией
      при set/remove feedback; тест `test_admin_quality_is_cached_on_second_request`.
      Списки/прогресс — прежний namespace `cache:tasks:*`, SCAN+DEL при мутациях.
- [x] **Зависит от:** S35-003 · **Оценка:** 3 ч (факт ~2 ч)

#### S39-004: Ёмкость и прогноз — `[x]`

- [x] `docs/CAPACITY.md`: методика, формулы, оценки и ограничения; реальный
      baseline на 1 реплике/2 воркерах ждёт nightly-runner. Локальный smoke
      (dev, 1 воркер) — в `docs/PERFORMANCE.md`.
- [x] Рекомендации: workers, pool size, лимиты контейнеров (S35-005), пороги
      масштабирования; ссылки на дашборды.
- [x] **Зависит от:** S39-001 · **Оценка:** 3 ч (факт ~2 ч)

#### S39-005: Входные лимиты и таймауты — `[x]`

- [x] `client_max_body_size` в nginx и `request_body` в Caddy; лимит
      `UploadFile` (размер и тип) в коде, а не только в надежде на прокси;
      тест 413.
- [x] Таймауты: `proxy_read_timeout` для LLM-стрима и WS (не рвать долгие
      ответы), `proxy_connect_timeout`, таймаут песочницы; значения — в
      `RULES.md`.
- [x] **Зависит от:** S36-003 · **Оценка:** 4 ч

#### S39-006: Документация и закрытие спринта — `[x]`

- [x] `DESIGN_ADMIN_AND_OPS`, `RULES.md`, `CHANGELOG.md`, `RELEASES.md`,
      отчёт `SPRINT-39.md`.
- [x] **Зависит от:** S39-001…S39-005 · **Оценка:** 2 ч

**DoD:** nightly-нагрузка с порогами p95/error rate (baseline заполняется
после первого runner-прогона); N+1 на ключевых эндпоинтах отсутствует
(query-count тесты); кэш качества работает и инвалидируется; ёмкость описана
(оценки + методика); 413/415 и таймауты проверены.

---

### Спринт 40: DX & Docs — `[x]` (завершён 2026-11-12)

**Цель:** новый разработчик поднимает проект по документации без вопросов, а
архитектурные решения зафиксированы в ADR.

**Зависит от:** спринты 33–39 (по мере готовности)  
**Оценка:** 2 дня  
**Отчёт:** `docs/reports/sprint-40/SPRINT-40.md`

#### S40-001: ADR — `[x]`

- [x] `docs/adr/README.md` + шаблон (Context / Decision / Consequences).
- [x] ADR-001…007: GHCR/digest, Caddy/edge, `TRUSTED_PROXIES` + refresh в
      теле, бэкапы systemd+age+S3, LLM guardrails, секреты `*_FILE`,
      CI-гейты/preflight/GitFlic. Покрыты и ранние решения (PostgreSQL+pgvector,
      песочница, наблюдаемость, MIT) через ссылки в ADR.
- [x] **Зависит от:** S36, S37, S38 · **Оценка:** 4 ч (факт ~3 ч)

#### S40-002: Онбординг с нуля — `[x]`

- [x] `docs/GETTING_STARTED.md` §2: обязательные ENV и новые настройки v0.6.0
      (`TRUSTED_PROXIES`, `SENTRY_DSN`, `DOCS_ENABLED`, `LLM_GUARDRAILS_ENABLED`,
      `*_FILE`, `MAX_UPLOAD_BYTES`, `RATE_LIMIT_ENABLED`, `CACHE_ENABLED`).
- [x] Чек-лист «первый запуск» и troubleshooting уже в документе; ссылки на
      `CONTRIBUTING.md`/ADR добавлены. Отдельный `make bootstrap` не вводили:
      используется `cp .env.example .env` + `docker compose`.
- [~] Полный прогон на чистой машине/WSL без кэша образов не выполнялся
      (в сессии нет чистого окружения); ограничение отражено в отчёте S40.
- [x] **Зависит от:** S33-007 · **Оценка:** 5 ч (факт ~2 ч)

#### S40-003: CONTRIBUTING, CODEOWNERS, шаблоны — `[x]`

- [x] `CONTRIBUTING.md`: ветки, Conventional Commits, preflight, `gates.sh`,
      тесты, env/секреты, PR и отчёты.
- [x] `.github/CODEOWNERS`, issue-шаблоны bug/feature, PR-шаблон со ссылками
      на `gates` и отчёт шага.
- [x] **Зависит от:** S37-005 · **Оценка:** 3 ч (факт ~2 ч)

#### S40-004: Дрейф `.env.example` ↔ `Settings` — `[x]`

- [x] `scripts/check_env_drift.py` (stdlib/AST, без импорта pydantic) сравнивает
      поля `Settings` и активные ключи `.env.example`; падает при missing/extra.
- [x] `.env.example` синхронизирован (76 полей); исключения: `version`
      (только код) и `UVICORN_WORKERS` (compose/uvicorn).
- [x] `backend/tests/test_env_drift.py` (4 теста) + шаг `env-drift` в
      `gates.sh`/`gates.ps1`, `backend-lint.sh`, GitHub CI и GitFlic;
      документировано в `CONTRIBUTING.md`, `RULES.md`.
- [x] **Зависит от:** S33-003, S34 · **Оценка:** 3 ч (факт ~2 ч)

#### S40-005: Актуализация документации — `[x]`

- [x] README/ARCHITECTURE: версия (последний релиз v0.5.0, этап v0.6.0),
      тесты/покрытие, миграции `001`–`022`, схема с Caddy/GHCR, кэш и лимиты.
- [x] `docs/README.md`: навигация на `DEPLOY`, `MONITORING`, `RUNBOOK`, `SLO`,
      `PERFORMANCE`, `CAPACITY`, `ASVS_L1`, ADR, `CONTRIBUTING`; проверены
      локальные ссылки.
- [x] `CHANGELOG.md` (S39–S40), `RELEASES.md` (черновик релиза v0.6.0),
      отчёты `docs/reports/sprint-40/`.
- [x] **Зависит от:** S40-001…S40-004 · **Оценка:** 4 ч (факт ~3 ч)

**DoD:** документация соответствует коду (версии/цифры/ссылки); ADR и шаблоны
готовы; env-drift ловится тестом и CI; навигация без мёртвых ссылок. Полный
онбординг на чистой машине остаётся ручной проверкой при первом внешнем
участнике (отражено в отчёте).

---

### Спринт 41: Release — `[ ]`

**Цель:** воспроизводимый релиз с проверенным обновлением и откатом.

**Зависит от:** спринты 33–40  
**Оценка:** 2,5 дня  
**Отчёт:** `docs/reports/sprint-41/SPRINT-41.md` + итог этапа
`docs/reports/v0.4.0/STAGE.md`

> Версия тега — **`v0.6.0`** (решение §10, вопрос 1, утверждено 2026-11-11). Имя
> каталога отчёта этапа сохраняется (`v0.4.0/`), чтобы не плодить сущности; в
> документе указывается и имя этапа, и фактический тег.

#### S41-001: Руководство по апгрейду — `[ ]`

- [ ] `docs/UPGRADE.md`: миграции (ожидаются 023), новые ENV (trusted proxy,
      Sentry, docs flag, backup/S3, workers), изменение `POST /auth/refresh`
      (query → body — **breaking**), новые compose-файлы (prod, release,
      monitoring), порядок деплоя, откат, restore.
- [ ] Проверить апгрейд на копии БД v0.5.0; зафиксировать время и проблемы.
- [ ] **Зависит от:** все спринты · **Оценка:** 5 ч

#### S41-002: Версия, CHANGELOG, документация — `[ ]`

- [ ] Версия в `pyproject.toml`, `frontend/package.json`,
      `backend/app/config.py`; `check_version` — 0 расхождений.
- [ ] `CHANGELOG.md` (раздел релиза, Breaking-блок), `RELEASES.md` (итог
      этапа), README/бейджи, ссылки на новые документы.
- [ ] **Зависит от:** S41-001 · **Оценка:** 3 ч

#### S41-003: Репетиция релиза — `[ ]`

- [ ] Полные гейты; сборка версионированных образов в GHCR; SBOM + checksums;
      деплой на staging по digest; smoke; откат; restore drill; замеры.
- [ ] Записать найденные проблемы; блокирующие — исправить до тега.
- [ ] **Зависит от:** S41-002 · **Оценка:** 6 ч

#### S41-004: Тег и релизы — `[ ]`

- [ ] Тег **`v0.6.0`** (решение §10, вопрос 1); GitHub Release + GitFlic Release; артефакты (SBOM,
      checksums, заметки); релизный workflow публикует образы с этим тегом.
- [ ] Post-release: `/health/ready`, `version`, smoke по HTTPS-домену,
      проверка документации и отката.
- [ ] **Зависит от:** S41-003 · **Оценка:** 3 ч

#### S41-005: Итоговый отчёт этапа — `[ ]`

- [ ] `docs/reports/sprint-41/SPRINT-41.md` и `docs/reports/v0.4.0/STAGE.md`:
      что вошло, метрики, KI, отклонения от аудита, уроки.
- [ ] Обновить `TODO_V0.4.md` (все статусы), `KNOWN_ISSUES.md`,
      `RELEASES.md`, `CHANGELOG.md`; сверить нумерацию с TODO_V0.7.md.
- [ ] **Зависит от:** S41-004 · **Оценка:** 2 ч

**DoD:** тег и оба релиза созданы; SBOM/checksums прикреплены; апгрейд с v0.5.0
проверен; откат и restore drill проверены; все гейты зелёные; итоговый отчёт
заполнен.

---

## 6. Сквозной DoD этапа

Этап считается завершённым, когда:

1. **Код и тесты:** `ruff check` — 0, `mypy app` — 0, полный `pytest` в
   собранном образе — зелёный; frontend `typecheck/lint/test/build` — зелёные;
   e2e — зелёные; `alembic check` — чистый.
2. **Supply chain:** все `FROM`/`image:`, включая релизные `ghcr.io`, закреплены
   по digest; `hadolint`/`trivy` — 0 HIGH/CRITICAL (или принято с expiry);
   SBOM прикреплён к релизу; Dependabot-долг разобран.
3. **High-риски:** `require_role` проверяет `is_active`; refresh только в теле;
   XFF не обходит лимит (`KI-032`…`KI-034` закрыты).
4. **Наблюдаемость:** scrape `/metrics`, Prometheus, Grafana, Loki, Sentry,
   алерты и SLO — в репозитории; `--profile monitoring` работает.
5. **Деплой/DR:** образы в GHCR по digest, на сервере нет сборки; HTTPS-домен,
   `:3000` не опубликован; deploy/rollback одной командой; миграции отдельным
   job'ом; бэкап по таймеру в S3 зашифрован; restore drill автоматизирован.
6. **Гейты:** красный PR не мержится (или `KI-023` `Blocked` с ручным
   fallback); coverage-гейт; `gates --full` воспроизводит CI.
7. **Безопасность:** ASVS L1 без открытых High; секретов в конфигах нет;
   публичный Swagger закрыт; `SECRET_KEY` fail-fast.
8. **Документация:** ADR, `DEPLOY.md`, `MONITORING.md`, `RUNBOOK.md`, `SLO.md`,
   `CAPACITY.md`, upgrade, `CHANGELOG`, `RELEASES`, отчёты; мёртвых ссылок нет.
9. **Релиз:** тег, GitHub/GitFlic Release, SBOM/checksums, post-release smoke и
   проверенный откат.

---

## 7. Критический путь и параллелизм

**Критический путь:** 33 → 34 → 35 → 36 → 41. Это ~17 инженерных дней из 29.

| Волна | Спринты | Условие старта |
|-------|---------|----------------|
| 1 | 33 (остаток) | v0.5.0; S33-001/002 закрыты |
| 2 | 34, 37 | 34 — сразу (не зависит от инфраструктуры); 37 — доступ владельца по `KI-023` |
| 3 | 35 | 34 (метрика блокировок) и 33 |
| 4 | 36 | 34 (trusted proxy), 35 (метрики бэкапов) |
| 5 | 38, 39, 40 | 36 (38), 35 (39), 33–39 (40) |
| 6 | 41 | все спринты 33–40 |

При одном разработчике «параллельные» ветки означают переключение между
задачами, а не одновременную работу. Действие владельца по `KI-023`
(агент/токен GitFlic или GitHub Pro) нужно начинать в начале этапа: это самый
длинный внешний lead time. Так же рано нужны: DNS-запись домена (S36-003),
S3-бакет и credentials (S36-006) — без них спринт 36 встанет.

---

## 8. Риски и меры

| Риск | Вероятность | Влияние | Мера |
|------|-------------|---------|------|
| `KI-023`: нет доступа к GitFlic-агенту/GitHub Pro | Высокая | Высокое | Начать в волне 2; fallback — ручной гейт + `gates.ps1|sh`; не блокировать остальные спринты |
| Офлайн/зависший self-hosted раннер | Высокая | Среднее | Preflight-пинг и таймауты (S37-004); локальные гейты как источники истины (S37-005) |
| Домен/DNS и ACME не готовы к S36-003 | Средняя | Высокое | Запросить DNS в волне 2; временно staging на self-signed, но релиз — только с валидным TLS |
| Порт 80/443 занят Caddy workflow-builder | Высокая | Среднее | Vhost в чужом Caddy по согласованию или отдельный Caddy на 8080/8443; ADR (S40-001) |
| S3/credentials Selectel не выданы | Средняя | Высокое | Бэкап сначала локально + шифрование; `--upload` включается, как только доступ есть; `BackupStale` не «зеленеет» фиктивно |
| Потеря приватного ключа `age` | Низкая | Высокое | Ключ у владельца, дубликат в менеджере секретов; restore drill проверяет расшифровку |
| Breaking-изменение refresh ломает клиентов/e2e | Средняя | Среднее | Один PR на backend+frontend, контрактный снапшот, UPGRADE, запись в CHANGELOG |
| Неверный `TRUSTED_PROXIES` схлопывает все IP в один | Средняя | Высокое | Пустое значение = не доверять; тесты «за прокси/без прокси»; smoke после деплоя (`audit` IP) |
| Sentry/Prometheus/Loki съедают RAM пилота (7,7 ГБ) | Средняя | Среднее | Лимиты (S35-005), профиль `monitoring` опционален, retention Prometheus/Loki ограничен |
| GHCR rate limits / приватность пакетов | Низкая | Среднее | PAT с нужными scope, документация в `DEPLOY.md`, кэш слоёв |
| Нестабильный PyPI/trivy DB/зеркала (`KI-017`) | Средняя | Среднее | wheelhouse, кэш, `--skip-db-update` по расписанию, повторяемые сборки |
| Мониторинг не поднят до деплоя → слепой прод | Средняя | Высокое | Жёсткий порядок волн: 35 до 36; DoD спринта 36 требует алерта `BackupStale` |
| Документация расходится с кодом | Средняя | Низкое | env-drift тест, `check_version`, обновление docs в DoD каждого шага |
| Путаница нумерации версий (этап «v0.4.0», тег `v0.6.0`) | Снята | Низкое | Решение §10, вопрос 1 утверждено 2026-11-11; ADR; единая запись в `RELEASES.md` |

---

## 9. Границы этапа (что не входит)

- **Multi-node, HA, Redis Sentinel/Cluster, HA PostgreSQL, active-active,
  Kubernetes/Swarm.** Сознательное сужение (аудит: пилот закрывается одним
  узлом; блокируют операции, не число реплик). Задачи sticky WS и
  агрегированных метрик сняты; `UVICORN_WORKERS=2` и multiprocess-метрики
  остаются в S35-001. Возврат — отдельным этапом после пилота.
- SSO/LDAP/SAML/SCIM, мультитенантность, биллинг и платежи.
- Мобильное приложение, PWA offline, новые языки интерфейса.
- Полный внешний пентест, WAF, SIEM; ASVS L1 — самостоятельная оценка с
  доказательствами, не сертификация.
- Перенос access/refresh-токенов в httpOnly-cookie/BFF, серверный logout и
  отзыв access по `token_version` — цель v0.7.0 (S51); в этом этапе `KI-027`
  остаётся `Accepted` с зафиксированным остатком.
- E-mail-верификация и сброс пароля — отложены в v0.7.0 (`KI-035`, решение
  владельца 2026-11-11).
- Guardrails ответов LLM и защита от prompt injection — обзор и критические
  фиксы в S38-006; системная разработка — v0.7.0 (`KI-036`).
- Подпись образов (cosign), SLSA L3, reproducible builds «бит-в-бит».
- Массовая замена `datetime.utcnow()` (~1400) — технический долг v0.7.0; в этом
  этапе не трогаем, чтобы не смешивать с hardening.
- Feature flags на пользователя, RAG v3/reranking, новые LLM-провайдеры.
- Email-deliverability (SPF/DKIM/DMARC) — эксплуатационная задача владельца.

---

## 10. Вопросы на согласование

**Статус: вопросы 1–5 закрыты владельцем 2026-11-11.** Ответы:

1. **Версионирование — решено.** Этап сохраняет имя «v0.4.0 Production
   Hardening» (по D-001), релиз выпускается как **`v0.6.0`**;
   [TODO_V0.6.md](TODO_V0.6.md) (спринты 49–52) сдвинут на **`v0.7.0`**
   ([TODO_V0.7.md](TODO_V0.7.md)).
2. **Multi-node — решено.** Вынесен за границы этапа (§9).
3. **Registry — решено.** **GHCR**.
4. **Размещение — решено.** Пилот — **текущий VPS**, наш Caddy на портах
   **8080/8443**; для публичного prod — **отдельный VPS**.
5. **E-mail-восстановление — решено.** Отложено: `KI-035` (Med), реализация —
   v0.7.0.

Открыты (рекомендации по умолчанию):

6. **Политика тегов образов.** `:<git-sha>` + `:vX.Y.Z` в релизе, `latest` —
   только вручную и никогда в prod-деплое.
7. **Оценка и порядок.** ~29 инженерных дней, волны §7; при сжатых сроках
   режем 39/40 (перф и DX), но **не** 34/35/36.

---

## 11. Отчётность и правила обновления плана

- Каждый шаг — отдельный отчёт `docs/reports/sprint-N/STEP-MM_<ТЕМА>.md`
  по `RULES.md` §12 (7 разделов).
- Каждый спринт — `docs/reports/sprint-N/SPRINT-N.md` по `RULES.md` §2.4,
  запись в `docs/RELEASES.md` и `docs/CHANGELOG.md`.
- Статусы задач обновляются здесь сразу после шага; оценки уточняются по
  факту, а не «подгоняются» задним числом.
- Если задача выросла больше чем на ~20% или меняется порядок спринтов —
  обновить этот файл и добавить запись в §12. Второй файл-план не создаётся.
- Новый блокер — сразу `KI-NNN` (следующий свободный — `KI-032`) и остановка
  шага; обходной путь фиксируется в KI и отчёте.
- Находки аудита не «растворяются»: каждая либо имеет задачу (§2), либо явно
  вынесена за границы с причиной (§9).

---

## 12. Журнал изменений плана

| Дата | Изменение |
|------|-----------|
| 2026-11-02 | Создан высокоуровневый план v0.4.0 (спринты 33–41), аудит практик, карта KI |
| 2026-11-05 | S33-001 (digest) и S33-002 (non-root) закрыты; добавлена детализация задач S33-003…S41-005, оценки, критический путь, риски, границы этапа и вопросы на согласование |
| 2026-11-05 | Создан план следующего этапа [TODO_V0.5.md](TODO_V0.5.md) (спринты 42–50); обновлён следующий свободный KI (`KI-031`) и ссылка на cookie/BFF (S45-006) |
| 2026-11-10 | Этап отложен по D-001 (этот файл не менялся; статус — в `RELEASES.md`) |
| 2026-11-11 | **Этап возобновлён после v0.5.0.** План пересобран по аудиту ноября 2026: базис v0.5.0, спринт 34 — High-риски (`require_role`/`is_active`, refresh в тело, trusted proxy; `KI-032`…`KI-034`), спринт 35 — scrape/Sentry/лимиты/SLO, спринт 36 — GHCR/digest/Caddy/TLS/deploy/rollback/бэкапы (systemd, S3, `age`, имя контейнера) и DR, 38 — ASVS и решения по e-mail/LLM-safety; multi-node вынесен в §9; добавлены таблица «аудит → задача», нумерация версий в §10, вопрос 1 |
| 2026-11-11 | **План утверждён владельцем:** релиз — **v0.6.0**, `TODO_V0.6.md` → `TODO_V0.7.md`; registry — GHCR; пилот — текущий VPS с Caddy 8080/8443, публичный prod — отдельный VPS; e-mail отложен (`KI-035`). Спринт 34 закрыт (`KI-032`…`KI-034`) |
| 2026-11-11 | Заведены `KI-032`…`KI-035`; `KI-032`…`KI-034` закрыты спринтом 34 |
| 2026-11-12 | Спринт 35 закрыт: 2 воркера + multiprocess-метрики, Sentry без PII (backend/frontend), Prometheus-правила и Grafana-дашборд как код, лимиты RAM/CPU и ротация логов, `docs/SLO.md` и `docs/MONITORING.md` |
| 2026-11-12 | Спринт 36 закрыт: GHCR-publish по тегам, digest-пиннинг в `.env.prod`, prod-compose без `build:` и с Caddy/TLS/WebSocket, `migrate` job, `deploy.sh`/`rollback.sh`, бэкапы с age/S3/systemd, `restore_drill.sh`, `docs/RUNBOOK.md` |
| 2026-11-12 | Спринт 37 (инженерия): preflight во всех self-hosted/GitFlic job'ах, coverage-гейты 70%, паритет CI и `gates.sh|ps1`, GitFlic-gate скрипт/инструкция; `KI-023` — `In Progress` до активации владельцем |
| 2026-11-12 | Спринт 38 закрыт: ASVS L1 + SECURITY_AUDIT + DPIA; секреты `*_FILE`/Docker secrets; CSP/HSTS/заголовки Caddy; guardrails LLM (KI-036) и защитные промпты; PRIVACY §8 |
| 2026-11-12 | Спринт 39 закрыт: nightly health/tasks/submit + baseline-заготовка, query-count тесты N+1, кэш `/admin/quality`, лимит 10 МБ и таймауты Caddy/nginx, `MAX_UPLOAD_BYTES`; PERFORMANCE/CAPACITY |
| 2026-11-12 | Спринт 40 закрыт: ADR-001…007, `CONTRIBUTING.md`/CODEOWNERS/шаблоны, env-drift (`check_env_drift.py` + тест + CI), актуализация README/ARCHITECTURE/навигации и черновик релиза v0.6.0; полный онбординг на чистой машине — ручная проверка |
