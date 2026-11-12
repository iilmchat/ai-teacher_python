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
| 35 | Observability & Monitoring | 33, 34 | 3,5 дня | `[ ]` | scrape, Sentry, Prometheus/Grafana/Loki, алерты, SLO, лимиты ресурсов |
| 36 | **Registry, Deploy, TLS & Backup/DR** | 35, 34 | 5,5 дня | `[ ]` | GHCR + digest, Caddy/TLS, deploy/rollback, миграции job'ом, бэкапы+DR |
| 37 | CI Gates & GitFlic | 33; `KI-023` | 3 дня | `[ ]` | required checks, паритет CI, coverage-гейт |
| 38 | Security & Privacy | 34, 36 | 3,5 дня | `[ ]` | DPIA, секреты, ASVS L1, e-mail-решение, LLM-safety |
| 39 | Performance & Capacity | 35 | 3 дня | `[ ]` | nightly-нагрузка, N+1, кэш, ёмкость, входные лимиты |
| 40 | DX & Docs | 33–39 | 2 дня | `[ ]` | ADR, онбординг, CONTRIBUTING, env-drift, актуализация docs |
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

### Спринт 35: Observability & Monitoring — `[ ]`

**Цель:** метрики, ошибки и трейсы реально собираются; алерты и дашборды лежат
в репозитории и поднимаются одной командой; ресурсы ограничены, логи не
съедают диск.

**Зависит от:** спринты 33, 34 (метрика `rate_limit_blocked_total`)  
**Оценка:** 3,5 дня  
**Отчёт:** `docs/reports/sprint-35/SPRINT-35.md`

#### S35-001: Scrape `/metrics` и multiprocess-режим — `[ ]`

- [ ] `docker-compose.monitoring.yml` (профиль `monitoring`): Prometheus
      scrapes `backend:8000/metrics` каждые 15 с; `/metrics` **не** публикуется
      наружу (nginx отдаёт 404, порт backend не публикуется — сохранить).
- [ ] `UVICORN_WORKERS` (prod default 2), `PROMETHEUS_MULTIPROC_DIR` в prod
      compose; каталог чистится entrypoint'ом (уже реализовано), у реплики свой.
- [ ] Интеграционный тест: 2 воркера, запросы, scrape; счётчики суммируются,
      гистограммы агрегируются, семантика gauge описана.
- [ ] `metrics_enabled` обязателен в prod; тест, что при выключенном флаге
      `/metrics` → 404.
- [ ] **Зависит от:** — · **Оценка:** 5 ч

#### S35-002: Sentry (backend + frontend) — `[ ]`

- [ ] Backend: `sentry-sdk[fastapi]`; `SENTRY_DSN`, `SENTRY_ENVIRONMENT`,
      `SENTRY_TRACES_SAMPLE_RATE`; `send_default_pii=False`; `before_send`
      вычищает email, токены, тексты промптов и код пользователя.
- [ ] Frontend: `@sentry/react`, тот же DSN через runtime-конфиг; source maps —
      артефактом CI (без публикации публично); release = версия + git-sha.
- [ ] No-op без DSN (тест `test_sentry.py`); ошибка Sentry не роняет запрос.
- [ ] Проверить CSP (`connect-src` для ingest-домена) и `docs/PRIVACY.md`:
      какие данные уходят в Sentry и на каком основании.
- [ ] **Зависит от:** — · **Оценка:** 5 ч

#### S35-003: Prometheus-правила и алерты как код — `[ ]`

- [ ] `deploy/monitoring/prometheus/{prometheus.yml,rules/alerts.yml,rules/recording.yml}`;
      `promtool check config` и `check rules` в CI (S37-002).
- [ ] Алерты: 5xx rate, p95 API, LLM error rate, sandbox timeouts, retention
      failures, DB pool saturation, target down, `BackupStale`, disk low,
      `RateLimitSpike`; `severity`, `runbook_url`, `summary`.
- [ ] Недостающие метрики: `backup_last_success_timestamp` (S36-006),
      `scheduler_last_success_timestamp`, `rate_limit_blocked_total` (S34-004).
- [ ] **Зависит от:** S35-001 · **Оценка:** 4 ч

#### S35-004: Grafana-дашборды как код — `[ ]`

- [ ] `deploy/monitoring/grafana/provisioning/{datasources,dashboards}`;
      JSON-дашборды: API overview, LLM/FinOps, sandbox, DB/Redis, ops/backups.
- [ ] Переменные `instance`, `route`, `provider`; единицы измерения и пороги
      соответствуют SLO.
- [ ] Smoke: Grafana поднимается с provisioning, панели получают данные;
      скриншот/описание — в `docs/MONITORING.md`.
- [ ] **Зависит от:** S35-003 · **Оценка:** 4 ч

#### S35-005: Лимиты CPU/RAM, логи и ротация — `[ ]`

- [ ] `deploy.resources.limits`/`reservations` для всех сервисов: app 2 ГБ,
      PostgreSQL 1 ГБ, Redis 128 МБ, Prometheus 512 МБ, Grafana 256 МБ, Loki —
      по профилю (аудит: пилот 7,7 ГБ, делим с workflow-builder).
- [ ] Docker logging `json-file` с `max-size: 10m`/`max-file: "3"` для всех
      сервисов; политика отсутствия PII в логах — ссылка из `RULES.md`.
- [ ] Профиль `monitoring` опционален: прод работает без него; проверка
      `docker stats` до/после лимитов — в отчёте.
- [ ] **Зависит от:** S35-001 · **Оценка:** 3 ч

#### S35-006: SLO и бюджеты ошибок — `[ ]`

- [ ] `docs/SLO.md`: SLI/SLO (доступность 99,5%/30 дней, p95 API ≤ 500 мс,
      submit p95 ≤ 2 с, успешные LLM-ответы ≥ 99%), error budget, burn-rate
      алерты, владелец.
- [ ] Связь «алерт → SLO → runbook»; ссылки из `DESIGN_ADMIN_AND_OPS` §10 и
      `docs/MONITORING.md` (без дублирования таблиц).
- [ ] **Зависит от:** S35-003 · **Оценка:** 3 ч

#### S35-007: Документация и закрытие спринта — `[ ]`

- [ ] `docs/MONITORING.md`: архитектура, команды, каталог алертов,
      troubleshooting, ограничения одного узла.
- [ ] `CHANGELOG.md`, `RELEASES.md`, отчёт `SPRINT-35.md`.
- [ ] **Зависит от:** S35-001…S35-006 · **Оценка:** 2 ч

**DoD:** `docker compose --profile monitoring up -d` поднимает Prometheus,
Grafana и Loki; все targets `UP`; правила и дашборды валидируются `promtool`;
Sentry ловит тестовую ошибку и не отправляет PII; SLO-документ есть; лимиты
CPU/RAM и ротация логов включены; прод работает без профиля `monitoring`.

---

### Спринт 36: Registry, Deploy, TLS & Backup/DR — `[ ]`

**Цель:** воспроизводимый артефакт в registry, закрытый TLS-периметр,
деплой/откат одной командой, автоматические бэкапы с off-site и проверенным
восстановлением. Самый дорогой спринт этапа — он снимает blocker'ы B2–B4.

**Зависит от:** спринты 34 (trusted proxy), 35 (метрики бэкапов, алерты)  
**Оценка:** 5,5 дня  
**Закрывает:** blocker'ы B2–B4 аудита  
**Отчёт:** `docs/reports/sprint-36/SPRINT-36.md`

#### S36-001: GHCR: сборка и публикация образов — `[ ]`

- [ ] Workflow `docker-publish` (или job в `release.yml`):
      `docker/build-push-action` для `backend`, `frontend`, `sandbox_runner` →
      `ghcr.io/<owner>/ai-teacher-{backend,frontend,sandbox-runner}`.
- [ ] Теги: `:<git-sha>`, `:vX.Y.Z`, `:latest` только для удобства ручного
      pull — в prod-деплое `latest` запрещён (S36-002). `permissions:
      packages: write`; кэш слоёв `type=gha`.
- [ ] `sandbox_runner` собирается в CI (аудит: контейнерный режим песочницы не
      собирается при деплое), digest-пиннинг base-образов сохраняется.
- [ ] Документация: `docs/DEPLOY.md` — логин в registry, видимость пакетов,
      ротация PAT, лимиты GHCR.
- [ ] **Зависит от:** S33-003 · **Оценка:** 5 ч

#### S36-002: Digest-пиннинг релизных образов — `[ ]`

- [ ] Деплой использует `image: ghcr.io/<owner>/ai-teacher-backend@sha256:...`;
      digest фиксируется в `.deploy-state` и в генерируемом
      `docker-compose.release.yml` (не руками).
- [ ] `scripts/ci/pin_release_images.py` (+ тесты): подставляет digest из
      `docker buildx imagetools inspect`; guard в CI — в prod compose нет
      `build:` для сервисов приложения и нет плавающих тегов.
- [ ] Обновить `check_image_pins.py`/guard: разрешены только digest-ссылки.
- [ ] **Зависит от:** S36-001 · **Оценка:** 4 ч

#### S36-003: Caddy, TLS и периметр — `[ ]`

- [ ] `deploy/caddy/Caddyfile`: домен, ACME (Let's Encrypt), `reverse_proxy
      frontend:80`, WebSocket upgrade (`/api/v1/chat/ws/`), `trusted_proxies`
      (совпадает с `TRUSTED_PROXIES` из S34-003), HSTS на HTTPS, security
      headers; HSTS из HTTP-ответов nginx убрать (остаётся на edge).
- [ ] Снять публикацию `:3000` на хост: frontend `expose: 80`; единственный
      публичный слушатель — Caddy (80/443). `HTTP_PORT` — только для локального
      запуска без Caddy.
- [ ] Если 80/443 заняты Caddy workflow-builder (пилот на общем VPS): vhost
      добавляется в его конфиг по согласованию с владельцем **или** поднимается
      отдельный Caddy на 8080/8443 — решение фиксируется ADR (S40-001).
- [ ] Проверки: `curl -I https://<домен>` (HSTS, редирект 80→443),
      WS-соединение через TLS, `testssl.sh`/SSL Labs без критичных замечаний.
- [ ] `frontend` healthcheck уже есть; добавить healthcheck Caddy-контейнера.
- [ ] **Зависит от:** S34-003 · **Оценка:** 5 ч

#### S36-004: Миграции отдельным job'ом — `[ ]`

- [ ] One-shot сервис `migrate` (`run --rm migrate`), приложение стартует с
      `SKIP_MIGRATIONS=true`; порядок «migrate → health → app»; ошибка миграции
      останавливает rollout и не оставляет полуприменённую схему.
- [ ] Таймаут и лог миграции; тесты на пустой БД и на уже применённой;
      `alembic check` остаётся гейтом.
- [ ] **Зависит от:** S36-001 · **Оценка:** 3 ч

#### S36-005: `deploy` и `rollback` — `[ ]`

- [ ] `scripts/deploy.ps1` + `deploy.sh`: preflight (`compose config`, ENV,
      свободное место, логин в GHCR), бэкап перед деплоем, pull по digest,
      migrate, `up -d`, health-gate `/health/ready`, smoke; `--dry-run`,
      `--no-backup`, `--version`, коды выхода.
- [ ] `.deploy-state` (gitignored): текущий и предыдущий digest; при ошибке —
      автоматический откат на предыдущий digest, повторный health-gate.
- [ ] Проверка отката на стенде: деплой «плохой» версии → автооткат → smoke
      зелёный; время отката зафиксировано в отчёте.
- [ ] **Зависит от:** S36-002, S36-004 · **Оценка:** 8 ч

#### S36-006: Бэкапы: systemd, S3, фикс имени контейнера — `[ ]`

- [ ] `scripts/backup.sh`: убрать неверный дефолт `ai_teacher_postgres`
      (аудит B4) — автоопределение через `docker compose -p <project> ps -q
      postgres` с fallback на `POSTGRES_CONTAINER`; ошибка, если контейнер не
      найден, вместо бэкапа пустоты.
- [ ] `--upload` в S3 (Selectel, префикс `ai-infra-backups/ai-teacher/`),
      шифрование `age` (публичный ключ в ENV, приватный — только у владельца),
      manifest + checksum, `--dry-run`, retention и на локальном диске, и в S3.
- [ ] systemd: `ai-teacher-backup.service` + `.timer` (ежедневно 03:00,
      `Persistent=true`, `OnFailure=` → уведомление), `EnvironmentFile=
      /etc/ai-teacher/backup.env`; для Windows-разработки — Task Scheduler.
- [ ] Метрика `backup_last_success_timestamp` (node-exporter textfile или
      pushgateway) → алерт `BackupStale` из S35-003.
- [ ] Тест: бэкап из prod-compose уходит в S3, архив расшифровывается,
      `pg_restore --list` читается.
- [ ] **Зависит от:** S35-003 · **Оценка:** 6 ч

#### S36-007: Автоматический restore drill — `[ ]`

- [ ] `scripts/restore-drill.sh|ps1`: последний бэкап (в т.ч. из S3) →
      scratch-БД → `pg_restore` → `alembic current` → проверки counts/health →
      удаление scratch; `--keep`, `--verify`, `--dry-run`.
- [ ] Ночной/недельный запуск и артефакт-отчёт (`docs/reports/dr/`); проверка,
      что drill не трогает рабочую БД (изолированный compose-проект).
- [ ] **Зависит от:** S36-006 · **Оценка:** 4 ч

#### S36-008: Runbook инцидентов — `[ ]`

- [ ] `docs/RUNBOOK.md`: БД недоступна, Redis, LLM, песочница, диск, TLS и
      сертификаты, GHCR-авторизация, бэкап/restore, откат; симптомы → проверки
      → действия → эскалация.
- [ ] Ссылки на дашборды/алерты/скрипты; обновить `DESIGN_ADMIN_AND_OPS` §10.
- [ ] **Зависит от:** S35-003, S36-002…S36-007 · **Оценка:** 4 ч

#### S36-009: Документация и закрытие спринта — `[ ]`

- [ ] `docs/DEPLOY.md` (полный цикл: сборка → registry → сервер → откат),
      `UPGRADE.md`, `GETTING_STARTED.md`, `RULES.md`; `CHANGELOG.md`,
      `RELEASES.md`, отчёт `SPRINT-36.md`.
- [ ] **Зависит от:** S36-001…S36-008 · **Оценка:** 2 ч

**DoD:** на сервере нет сборки из исходников — только pull по digest; сайт
доступен по HTTPS-домену, `:3000` не опубликован, HSTS только по TLS; откат на
предыдущий digest — одна команда, проверен на стенде; миграции отдельным job'ом;
бэкап уходит в S3 зашифрованным по systemd-таймеру, алерт `BackupStale` связан с
реальной метрикой; restore drill зелёный; runbook покрывает ключевые инциденты.

---

### Спринт 37: CI Gates & GitFlic — `[ ]`

**Цель:** красный PR физически не мержится; все гейты воспроизводимы локально;
паритет GitHub ↔ GitFlic.

**Зависит от:** спринт 33; действие владельца по `KI-023`  
**Оценка:** 3 дня (часть может быть `Blocked`)  
**Закрывает:** `KI-023` — при наличии доступа владельца  
**Отчёт:** `docs/reports/sprint-37/SPRINT-37.md`

> **Контекст:** зависший CI из-за офлайн-раннера не считается блокером этапа
> (решение владельца). Но required checks без живого раннера бессмысленны,
> поэтому S37-001 и S37-004 включают health-check раннера и таймауты.

#### S37-001: GitFlic-агент и required checks (`KI-023`) — `[ ]`

- [ ] Владелец: зарегистрировать PowerShell/Docker-агент, выдать токен, включить
      MR-пайплайн и «проверять статус последнего конвейера».
- [ ] Проверить на тестовом MR, что красный конвейер блокирует merge; если нет —
      gate через webhook/скрипт, решение — в `docs/CI.md`.
- [ ] Если доступа нет к началу спринта: `KI-023` остаётся `Blocked`, фиксируем
      fallback (ручной гейт + `gates.ps1|sh`), не имитируем гейт.
- [ ] **Зависит от:** доступ владельца · **Оценка:** 6 ч + ожидание

#### S37-002: Паритет GitHub ↔ GitFlic — `[ ]`

- [ ] Сопоставить job'ы (lint, test, frontend, security, e2e, docker,
      supply-chain, promtool) с этапами GitFlic: одинаковые команды, образы,
      кэш, артефакты.
- [ ] `gitflic-ci.yaml` — digest-пиннинг, path-фильтры, `needs`, таймауты;
      убрать расхождения и мёртвые job'ы.
- [ ] **Зависит от:** S33-003 · **Оценка:** 5 ч

#### S37-003: Coverage-гейт — `[ ]`

- [ ] Backend: `pytest --cov=app --cov-report=xml --cov-fail-under=70` в CI;
      отчёт — артефакт, порог не снижать без записи в KI.
- [ ] Frontend: thresholds в конфиге Vitest (lines/functions/branches/
      statements), отчёт в CI.
- [ ] **Зависит от:** S37-002 · **Оценка:** 3 ч

#### S37-004: Скорость и надёжность CI — `[ ]`

- [ ] `timeout-minutes`, `concurrency: cancel-in-progress`, кэш pip/pnpm,
      Docker layer cache, разумный retention артефактов.
- [ ] Preflight-проверка доступности self-hosted раннера (быстрый ping-job) и
      fail-fast по таймауту вместо «висящего» прогона; политика ручного
      перезапуска при офлайне — в `docs/CI.md`.
- [ ] Цель: lint+test+frontend < 15 мин; измерить до/после, записать.
- [ ] **Зависит от:** S37-002 · **Оценка:** 3 ч

#### S37-005: Единый локальный прогон гейтов — `[ ]`

- [ ] `scripts/ci/gates.ps1` + `gates.sh`: `--fast` (lint/type/unit), `--full`
      (+ e2e, docker, supply-chain, coverage, promtool), `--ci` (без
      интерактива), JSON-сводка; коды выхода.
- [ ] `make release-check` вызывает тот же скрипт; список гейтов совпадает с CI
      (проверка тестом/скриптом).
- [ ] **Зависит от:** S37-002 · **Оценка:** 4 ч

#### S37-006: Документация и закрытие спринта — `[ ]`

- [ ] `RULES.md` §10, `docs/CI.md`, `KNOWN_ISSUES.md` (`KI-023`),
      `CHANGELOG.md`, `RELEASES.md`, отчёт `SPRINT-37.md`.
- [ ] **Зависит от:** S37-001…S37-005 · **Оценка:** 2 ч

**DoD:** красный MR не мержится (проверено тестовым MR) или `KI-023` явно
`Blocked` с работающим ручным fallback; coverage-гейт активен; локальный
`gates --full` совпадает с CI; CI укладывается в целевое время; офлайн раннера
не подвешивает гейт.

---

### Спринт 38: Security & Privacy — `[ ]`

**Цель:** подтвердить ASVS L1, убрать секреты из конфигов, принять явные
решения по e-mail-восстановлению и безопасности ответов LLM для детей.

**Зависит от:** спринты 34, 36  
**Оценка:** 3,5 дня  
**Отчёт:** `docs/reports/sprint-38/SPRINT-38.md`

> Задачи, закрытые в спринте 34 (is_active, refresh, XFF, `SECRET_KEY`,
> Swagger), здесь только **проверяются в ASVS** — второй раз не фиксятся.

#### S38-001: Инвентаризация PII и DPIA — `[ ]`

- [ ] Инвентаризация: email, имя, чаты, код, эмбеддинги, audit IP; где
      хранится, срок, кто обработчик (DeepSeek/LLM), трансграничная передача;
      что уходит в Sentry (S35-002).
- [ ] `docs/DPIA.md`: цели, правовое основание, права субъекта, меры защиты,
      остаточные риски; приложение-ссылка из `docs/PRIVACY.md`.
- [ ] **Зависит от:** S35-002 · **Оценка:** 4 ч

#### S38-002: Секреты вне конфигов — `[ ]`

- [ ] Docker secrets / `*_FILE` для `SECRET_KEY`, `DEEPSEEK_API_KEY`,
      `POSTGRES_PASSWORD`, SMTP/S3-credentials; приоритет file над ENV.
- [ ] `docker-compose.prod.yml`: secrets вместо открытых значений; процедура
      ротации; стартовая валидация небезопасных значений.
- [ ] Тесты на `_FILE` и приоритет; `gitleaks` остаётся гейтом.
- [ ] **Зависит от:** S34-005 · **Оценка:** 6 ч

#### S38-003: OWASP ASVS L1 — `[ ]`

- [ ] `docs/ASVS_L1.md`: чек-лист с доказательствами (auth, session, access
      control, validation, crypto, errors/logging, data protection,
      configuration); ссылки на тесты и коммиты, включая S34-001…S34-006.
- [ ] Открытые пункты — в `KNOWN_ISSUES.md` с severity и планом; без «галочек»
      без доказательств.
- [ ] **Зависит от:** S38-001, S38-002, S36-003 · **Оценка:** 5 ч

#### S38-004: CSP/security headers после TLS и мониторинга — `[ ]`

- [ ] Проверить CSP/заголовки после появления Caddy, Sentry и WS; добавить
      `Cross-Origin-Opener-Policy`/`Cross-Origin-Resource-Policy`, если не ломают
      Monaco и API.
- [ ] HSTS — только при реальном TLS (S36-003); убрать дубль из nginx;
      проверка `curl -I` в smoke.
- [ ] **Зависит от:** S36-003 · **Оценка:** 3 ч

#### S38-005: Верификация e-mail и сброс пароля — решение — `[ ]`

- [ ] Аудит H9: восстановление аккаунта сейчас невозможно (только смена пароля
      изнутри). Оценить стоимость: SMTP-провайдер/домен, шаблоны писем,
      rate-limit на отправку, токены с TTL, анти-энумерация.
- [ ] Если SMTP и домен доступны в этапе — минимальная реализация:
      `POST /auth/password/forgot` (всегда 202), `POST /auth/password/reset`,
      `POST /auth/email/verify`; иначе — `KI-035` (Med) и перенос в v0.6.0.
- [ ] Решение и обоснование — ADR (S40-001), не «устное».
- [ ] **Зависит от:** S36-003 · **Оценка:** 4 ч (без реализации) / +8 ч при реализации

#### S38-006: Безопасность ответов LLM для детей — обзор — `[ ]`

- [ ] Аудит H10: prompt injection через код ученика/задания, отсутствие
      guardrails на ответы (кроме эвристики «не давать готовый код»), поведение
      при утечке системного промпта.
- [ ] Прогнать сценарии атак на текущий `LLMService` + модерацию S47; список
      пробелов и приоритетов → `KI-036` (Med) и задачи v0.6.0.
- [ ] Если найдено критичное (обход модерации, выдача кода целиком) — фикс
      входит в этот спринт, а не откладывается.
- [ ] **Зависит от:** — · **Оценка:** 4 ч

#### S38-007: Документация и закрытие спринта — `[ ]`

- [ ] `SECURITY.md`, `PRIVACY.md`, `RULES.md`, `KNOWN_ISSUES.md`,
      `CHANGELOG.md`, `RELEASES.md`, отчёт `SPRINT-38.md`.
- [ ] **Зависит от:** S38-001…S38-006 · **Оценка:** 2 ч

**DoD:** ASVS L1 пройден без открытых High; секретов в конфигах нет; `KI-035` и
`KI-036` заведены (или закрыты реализацией); CSP/HSTS проверены на реальном TLS;
DPIA и инвентаризация PII готовы.

---

### Спринт 39: Performance & Capacity — `[ ]`

**Цель:** известна ёмкость узла, регресс ловится nightly, входные лимиты не
позволяют одному запросу съесть память или соединение.

**Зависит от:** спринт 35  
**Оценка:** 3 дня  
**Отчёт:** `docs/reports/sprint-39/SPRINT-39.md`

#### S39-001: Нагрузочный тест в nightly — `[ ]`

- [ ] Расширить `scripts/load_test.py`: submit, chat/stream, list/detail,
      смешанный сценарий; пороги p95/RPS/error rate; baseline в
      `docs/reports/perf/baseline.json`.
- [ ] Nightly workflow (GitHub + GitFlic), падение при регрессе > 20%;
      отчёт-артефакт с сырыми цифрами.
- [ ] **Зависит от:** S35-001 · **Оценка:** 6 ч

#### S39-002: N+1 и индексы — `[ ]`

- [ ] `pg_stat_statements` в dev/compose, сбор топ-запросов; SQLAlchemy echo в
      тестах; query-count проверки для ключевых эндпоинтов.
- [ ] `EXPLAIN` для медленных запросов; недостающие индексы — миграцией
      (следующая свободная, ожидается 023); без индексов «на всякий случай».
- [ ] **Зависит от:** S35-001 · **Оценка:** 6 ч

#### S39-003: Кэш: hit-rate и инвалидация — `[ ]`

- [ ] Цель hit-rate (например, ≥ 70% для справочных данных); метрики
      `cache_hits_total`/`cache_misses_total`, панель и алерт.
- [ ] Инвалидация по тегам/версиям ключей, защита от stampede; тесты на
      консистентность (Redis общий для воркеров одной реплики).
- [ ] **Зависит от:** S35-003 · **Оценка:** 3 ч

#### S39-004: Ёмкость и прогноз — `[ ]`

- [ ] `docs/CAPACITY.md`: RPS на узел, p95, соединения БД, память/CPU, рост
      диска, прогноз с учётом retention; замер на 1 реплике с 2 воркерами.
- [ ] Рекомендации: workers, pool size, лимиты контейнеров (S35-005), пороги
      масштабирования; ссылки на дашборды.
- [ ] **Зависит от:** S39-001 · **Оценка:** 3 ч

#### S39-005: Входные лимиты и таймауты — `[ ]`

- [ ] `client_max_body_size` в nginx и `request_body` в Caddy; лимит
      `UploadFile` (размер и тип) в коде, а не только в надежде на прокси;
      тест 413.
- [ ] Таймауты: `proxy_read_timeout` для LLM-стрима и WS (не рвать долгие
      ответы), `proxy_connect_timeout`, таймаут песочницы; значения — в
      `RULES.md`.
- [ ] **Зависит от:** S36-003 · **Оценка:** 4 ч

#### S39-006: Документация и закрытие спринта — `[ ]`

- [ ] `DESIGN_ADMIN_AND_OPS`, `RULES.md`, `CHANGELOG.md`, `RELEASES.md`,
      отчёт `SPRINT-39.md`.
- [ ] **Зависит от:** S39-001…S39-005 · **Оценка:** 2 ч

**DoD:** nightly-нагрузка зелёная с порогами и baseline; N+1 на ключевых
эндпоинтах отсутствует; hit-rate кэша измеряется; ёмкость узла описана цифрами;
413/таймауты проверены.

---

### Спринт 40: DX & Docs — `[ ]`

**Цель:** новый разработчик поднимает проект по документации без вопросов, а
архитектурные решения зафиксированы в ADR.

**Зависит от:** спринты 33–39 (по мере готовности)  
**Оценка:** 2 дня  
**Отчёт:** `docs/reports/sprint-40/SPRINT-40.md`

#### S40-001: ADR — `[ ]`

- [ ] `docs/adr/README.md` + шаблон (Context / Decision / Consequences).
- [ ] ADR: платформа CI, изоляция песочницы, метрики/наблюдаемость,
      PostgreSQL+pgvector, лицензия MIT, секреты; **новые**: GHCR как registry,
      Caddy и владение портом 80/443 (S36-003), версионирование этапа (§10, вопрос 1),
      режим без multi-node (§9), e-mail-восстановление (S38-005).
- [ ] **Зависит от:** S36, S37, S38 · **Оценка:** 4 ч

#### S40-002: Онбординг с нуля — `[ ]`

- [ ] Пройти `GETTING_STARTED.md` на чистой машине/WSL без кэша образов и venv;
      замерить время; починить пробелы.
- [ ] `make bootstrap` (опционально), чек-лист «первый запуск», ссылки на
      troubleshooting.
- [ ] **Зависит от:** S33-007 · **Оценка:** 5 ч

#### S40-003: CONTRIBUTING, CODEOWNERS, шаблоны — `[ ]`

- [ ] `CONTRIBUTING.md`: ветки, коммиты, гейты, отчёты, ревью, релиз.
- [ ] `.github/CODEOWNERS`, issue-шаблоны (bug/feature), PR-шаблон со ссылками
      на `gates` и отчёт.
- [ ] **Зависит от:** S37-005 · **Оценка:** 3 ч

#### S40-004: Дрейф `.env.example` ↔ `Settings` — `[ ]`

- [ ] Тест: парсит `Settings.model_fields` и `.env.example`, проверяет
      наличие/отсутствие ключей; allowlist для compose-only переменных.
- [ ] Учесть новые ENV: `TRUSTED_PROXIES`, `SENTRY_*`, `DOCS_ENABLED`,
      `RATE_LIMIT_*`, `BACKUP_*`, `UVICORN_WORKERS`, `PROMETHEUS_MULTIPROC_DIR`.
- [ ] Тест в CI; документировать в `RULES.md`.
- [ ] **Зависит от:** S33-003, S34 · **Оценка:** 3 ч

#### S40-005: Актуализация документации — `[ ]`

- [ ] README/ARCHITECTURE: актуальные цифры (тесты, 22+ миграции, версия),
      схема деплоя с Caddy и GHCR; убрать устаревшие утверждения (аудит Medium).
- [ ] `docs/README.md`: навигация на `DEPLOY.md`, `MONITORING.md`, `RUNBOOK.md`,
      `SLO.md`, `CAPACITY.md`, `ASVS_L1.md`, ADR; проверка мёртвых ссылок.
- [ ] `CHANGELOG.md`, `RELEASES.md`, отчёт `SPRINT-40.md`.
- [ ] **Зависит от:** S40-001…S40-004 · **Оценка:** 4 ч

**DoD:** чистая машина проходит онбординг по docs; ADR и шаблоны готовы;
env-drift ловится тестом; навигация без мёртвых ссылок; README соответствует
коду.

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
