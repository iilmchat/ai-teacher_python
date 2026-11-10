## 4. `ai-teacher_python` — платформа обучения Python

**Состояние:** ветка `sprint/43-chat-productivity`; рабочее дерево грязное —
24 изменённых и 9 неотслеживаемых файлов спринта 47, в `origin/main` не
смержено. Воспроизводимого артефакта для деплоя нет — это blocker №0.
**Стек:** Python 3.12 / FastAPI 0.162, React 19 / Vite 6, PostgreSQL 17 +
pgvector, Redis 7, Alembic (22 миграции), Monaco, WebSocket, in-process
sandbox. 20+ таблиц.
**Код/эксплуатация:** ~75–80% / ~35–40%.

### Что уже хорошо

- 633 backend-теста, 267 frontend, 36 e2e; coverage gate 70%, контрактный
  снапшот OpenAPI, нагрузочные тесты (0.5 RPS в PR, 2 RPS nightly).
- Песочница 6 слоёв (AST → RestrictedPython → subprocess → RLIMIT/Job Object
  → семафор/пул → контейнер), 36 тестов атак; p95 анализа 49 мс после пула.
- Дисциплина Alembic: `alembic check`, тест downgrade→upgrade, паритет
  моделей и миграций.
- `/health/live`, `/health/ready` (БД+Redis, 503), Prometheus-метрики (HTTP,
  LLM, песочница, пул БД), structlog с `request_id`.
- Retention-планировщик с advisory-lock; экспорт/удаление/анонимизация
  данных, audit-log, `docs/PRIVACY.md`.
- Backup/restore-скрипты с проверкой архива; digest-пиннинг базовых образов,
  non-root backend, pip-audit/pnpm audit/gitleaks/Dependabot.
- prod-compose: БД/Redis без публикации, обязательные
  `POSTGRES_PASSWORD`/`SECRET_KEY`, `DEBUG=false`.

### Блокеры

1. **Нет воспроизводимого артефакта:** спринт 47 не закоммичен и не смержен;
   ветка отличается от `origin/main`.
2. **Нет registry/CD/deploy/rollback:** CI собирает образы локально, на
   сервере — сборка из исходников; digest не фиксируется.
3. **Нет TLS/домена/edge:** prod отдаёт HTTP на `:3000`, HSTS по HTTP;
   публикация порта на хост обходит Caddy.
4. **Бэкапы не автоматизированы:** нет cron/systemd, шифрования, offsite;
   `scripts/backup.sh` привязан к dev-имени `ai_teacher_postgres`, а в prod
   контейнер называется иначе.

### High

- **Refresh-токен в query string** (`POST /auth/refresh?refresh_token=...`)
  → утечка в access-логи.
- **Токены в localStorage**, logout — no-op, access не отзывается до 30 мин
  (KI-027).
- **Обход rate-limit** подделкой `X-Forwarded-For`; 300/мин на IP общий для
  класса за NAT; `/code/execute` без per-user лимита.
- **Нет подтверждения e-mail и сброса пароля** — восстановление аккаунта
  невозможно.
- **Нет контент-безопасности ответов LLM для детей** и защиты от prompt
  injection (есть только эвристика «не давать готовый код»).
- **Мониторинг не подключён:** метрики есть, но нет scrape, алертов,
  дашбордов, Sentry/OTel; `SECRET_KEY` по умолчанию не валит старт.
- **`require_role` использует `get_current_user`** — деактивированный
  teacher/admin сохраняет доступ до истечения access-токена.

### Medium (выборочно)

Один uvicorn-воркер; нет лимитов CPU/RAM и ротации логов; `UploadFile`
читается в память без лимита; Swagger/OpenAPI публичны; наивные
`datetime.utcnow()` (~1400); миграции при каждом старте;
README/ARCHITECTURE устарели (538 тестов/013 миграций вместо 633/022);
нет healthcheck в Dockerfile; нет body-size/timeouts в nginx; контейнерный
режим песочницы не собирается при деплое; refresh без отдельного лимита.

### Оценка

| Путь | Дней |
|---|---|
| Безопасный закрытый пилот (1 класс, после merge) | **7–9** |
| Устойчивый production | **17–26** (~4–5 недель) |

Снижение относительно «с нуля» (22–33 дня) — за счёт уже собранного prod
kit на workflow-builder: Caddy, GHCR, S3-бэкапы, Prometheus, SMTP,
deploy/rollback.

**Ресурсы:** минимум 2 vCPU / 2–3 ГБ; рекомендуется 4 vCPU / 8 ГБ; диск
40 ГБ. GPU не нужен (DeepSeek); LM Studio — опциональный fallback.

### Размещение

- **Пилот:** новый FirstVDS `94.250.252.142` (4 vCPU / 7.7 ГБ / 79 ГБ).
  Фактически свободно ~7.2 ГБ RAM, CPU ~2.5%, диск ~16% — teacher с
  лимитами (app 2 ГБ, PG 1 ГБ, Redis 128 МБ) помещается рядом с
  workflow-builder. Минус: общий CPU и blast radius, Caddy принадлежит
  workflow-builder.
- **Публичный/школьный prod:** отдельный VPS 2–4 vCPU / 4–8 ГБ (FirstVDS
  NVMe 2/4/60 ≈ 1 069 ₽/мес) — чище по изоляции и соответствию 152-ФЗ.
- **Не размещать:** резерв `62.109.1.230` (VetAssistant + мониторинг),
  primary `89.108.70.62` (два прода), мини-ПК (только staging).

### Вердикт

**Почти готов как закрытый пилот, не готов к публичному production.** Код
зрелый: тесты, песочница, миграции, метрики, приватность. Блокируют не
архитектура, а отсутствие воспроизводимого деплоя, TLS, автоматических
бэкапов и мониторинга, плюс утечка refresh-токена и обходимый rate-limit.

**5 действий:**
1. Закоммитить/смержить спринт 47 и зафиксировать тег/артефакт.
2. GHCR + digest-пиннинг + deploy/rollback; Caddy-vhost; снять публикацию
   `:3000`.
3. Бэкапы: починить имя контейнера, systemd-таймер, age-шифрование,
   Selectel S3 `ai-infra-backups/ai-teacher/`, restore-дрилл.
4. Auth/anti-abuse: refresh вне query string, trusted proxy для XFF,
   per-user лимиты на `/code/execute` и `/auth/refresh`, fail-fast
   `SECRET_KEY`.
5. Наблюдаемость и детская безопасность: scrape `/metrics` + алерты +
   Sentry, e-mail verification/reset, модерация/guardrails LLM, согласия
   152-ФЗ.
