# TODO_V0.3.md — план разработки v0.3.0 (спринты 21–30)

> Третий этап проекта. Продолжение [TODO_V0.2.md](TODO_V0.2.md) (v0.2.0 «Classroom»,
> спринты 11–20 завершены). Правила работы — [docs/RULES.md](docs/RULES.md).
> Контракты — [docs/SPEC.md](docs/SPEC.md).
>
> Статусы: `[ ]` — не начато, `[~]` — в работе, `[x]` — завершено,
> `[!]` — блокер (см. [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md))

**Целевая версия:** v0.3.0 «Ops & Scale»  
**Создан:** 2026-10-30  
**Текущий спринт:** этап v0.3.0 завершён — релиз `v0.3.0` «Ops & Scale»
(спринты 21–30)  
**Базис:** v0.2.0 (2026-10-30)  
**Текущее состояние:** **460** backend-тестов (+1 skip на Windows), 80 frontend-unit
+ 12 e2e, миграции до `010`; CI — 7 job'ов (вкл. perf-smoke) на self-hosted
runner'е; `pip-audit` без игноров; активных KI — 2: `KI-018` (`.format` в
песочнице, Low, accepted), `KI-023` (merge-gate/авто-мерж, High).
Следующий свободный номер — **KI-024**.

---

## 0. Цели этапа

v0.2.0 сделал продукт пригодным для класса. v0.3.0 делает его **эксплуатируемым
и масштабируемым**: зелёный CI как обязательное условие мержа, современные
зависимости, предсказуемая песочница под нагрузкой, наблюдаемость, приватность
и закрытие UX-остатков.

| Направление | Что должно появиться к v0.3.0 |
|-------------|-------------------------------|
| Процесс | CI снова запускает job'ы и блокирует мерж; релиз — одна кнопка/команда |
| Зависимости | `fastapi` 0.162+ / `starlette` 1.x (KI-015), `pytest` 9.x (KI-016), 0 accepted-vuln без обоснования |
| Производительность | submit 5 RPS, p95 ≤ 2 с (KI-022) — батчинг кейсов + пул раннеров |
| Изоляция | песочница в отдельном контейнере (runner), non-root, без сети, read-only FS |
| Эксплуатация | `/metrics`, request-id, liveness/readiness, audit log действий teacher/admin |
| Данные | экспорт CSV/JSON, retention-политика, удаление аккаунта, заметка о ПДн |
| Продукт | поиск по чату в UI, массовые назначения, журнал оценок, email-уведомления (опц.) |
| UX | карточный вид таблиц, 100% локализация, авто-проверка контраста и a11y |

**Принципы этапа:**

1. **Сначала процесс, потом риск.** Спринт 21 возвращает CI — только после этого
   начинаются мажорные апгрейды (22) и изменения песочницы (23–24).
2. **Апгрейд без контрактных тестов запрещён.** Перед `fastapi`/`starlette`
   фиксируем OpenAPI-снапшот и ответы ключевых эндпоинтов (S22-001).
3. **Производительность измеряется, а не обещается.** Любая оптимизация submit
   подтверждается `scripts/load_test.py` и цифрами в отчёте.
4. **Обратная совместимость API v1.** Новые поля — аддитивно; breaking changes —
   только через `/api/v2` и отдельное решение.
5. **Приватность — часть DoD.** Данные учеников: минимум PII, retention, экспорт
   и удаление по запросу.

---

## 1. Карта закрытия открытых проблем

| KI | Severity | Суть | Спринт | План |
|----|----------|------|--------|------|
| KI-014 | High | GitHub Actions не запускает job'ы (биллинг) | 21 | **закрыто**: self-hosted runner + `ci-selfhosted.yml`, 6/6 зелёные; merge-gate вынесен в KI-023 |
| KI-015 | High | `starlette 0.41.3` (транзитивно от `fastapi 0.115.5`) | 22 | координированный апгрейд `fastapi` + `starlette`, `pip-audit` без игнора |
| KI-016 | Low | dev-only advisory `pytest 8.3.3` | 22 | `pytest` 9.x + плагины, полный прогон |
| KI-017 | Low | PyPI недоступен с хоста разработки | 22 | `scripts/wheelhouse.py` (офлайн-установка из Docker), документация; **в CI уже офлайн-wheelhouse** (S21) |
| KI-018 | Low | `.format()` запрещён в песочнице (RP 8.5) | — | остаётся accepted; подсказка ученику уже есть (SPEC §5) |
| KI-022 | Med | submit ≈2 RPS (песочница) | 23 | батчинг кейсов в одном процессе + пул; цель 5 RPS, p95 ≤ 2 с |
| KI-023 | High | merge-gate: GitHub Free не даёт required checks, GitFlic ждёт токен/агент | 21 (перенос в 22) | `scripts/ci/protect-branch.ps1` (после Pro) или MR-гейт GitFlic; до этого — RULES §10 |

Новые проблемы заводим сразу с `KI-NNN` (следующий свободный — **KI-024**).
Ожидаемые кандидаты: SMTP-зависимость уведомлений, лимиты Prometheus-метрик в
памяти процесса, тонкости seccomp в контейнере-раннере.

---

## 2. Оглавление

21. [Спринт 21: CI & Quality Gates](#спринт-21-ci--quality-gates--восстановление-ki-014)
22. [Спринт 22: Dependency Modernization](#спринт-22-dependency-modernization-ki-015016017)
23. [Спринт 23: Sandbox Throughput](#спринт-23-sandbox-throughput-ki-022)
24. [Спринт 24: Sandbox Runner Isolation](#спринт-24-sandbox-runner-isolation)
25. [Спринт 25: Observability & Audit Log](#спринт-25-observability--audit-log)
26. [Спринт 26: Export, Retention & Privacy](#спринт-26-export-retention--privacy)
27. [Спринт 27: RAG v2 & Search UX](#спринт-27-rag-v2--search-ux)
28. [Спринт 28: Teacher & Classroom v3](#спринт-28-teacher--classroom-v3)
29. [Спринт 29: UX, A11y & i18n Completion](#спринт-29-ux-a11y--i18n-completion)
30. [Спринт 30: Release v0.3.0](#спринт-30-release-v030)
31. [Сквозные требования (DoD)](#сквозные-требования-dod)
32. [Оценка трудозатрат](#оценка-трудозатрат)
33. [Что не входит в этап](#что-не-входит-в-этап)
34. [Риски этапа](#риски-этапа)

---

## Спринт 21: CI & Quality Gates — восстановление (KI-014)

**Цель:** PR нельзя смержить без зелёных проверок; CI снова работает и стоит
предсказуемо. Закрывает KI-014.

**Зависит от:** v0.2.0  
**Оценка:** 2.5 дня (включая пилот GitFlic)

### 21.0. Варианты CI-платформы (решение принимается по итогам S21-002)

| Вариант | Плюсы | Минусы | Стоимость для нас |
|---------|-------|--------|-------------------|
| **GitHub Actions + self-hosted runner** на машине проекта | нулевая миграция, PR checks и `gh`-скрипты остаются, привычный CI | зависимость от GitHub (биллинг/санкции), машина должна быть включена | 0 ₽ |
| **GitFlic SaaS + свой агент** (PowerShell/Docker) | RU-хостинг, реестр отечественного ПО, CI/CD в бесплатном плане (приватный репо ≤5 человек, 4 ГБ), GitLab-подобный `gitflic-ci.yaml` (services/DinD/cache/artifacts/MR-пайплайны/release), импорт с GitHub, зеркала PULL/PUSH | облачные агенты по умолчанию выключены; зеркало в облаке обновляется раз в сутки и создаётся по запросу в поддержку; MR/issues/wiki не переносятся; встроенный Gitleaks — только self-hosted; SAST/merge trains/аудит — платные тарифы | 0 ₽ (свой агент); Company — от 750 ₽/чел/мес |
| **GitFlic Self-hosted Community** | полный контроль, RU, неограниченно пользователей, CI/CD и агенты, LDAP/SSO OIDC | нужен сервер (1 ядро/2 ГБ/10 ГБ, Java 11, PostgreSQL 11+, Redis 6+) и его эксплуатация | 0 ₽ (Community); Pro — от 243 000 ₽/год |
| **GitLab CE self-hosted** / GitLab.com | зрелый CI, полный перенос MR/issues (CE) | тяжёлая эксплуатация; санкционные/доступностные риски облака | сервер |
| **Только локальные гейты** | ничего не нужно | нет required checks, регресс в `main` | 0 ₽ |

**Факты по GitFlic (проверено по документации и тарифам, 2026-10-30):**

- Тарифы: SaaS Free — публичные репозитории безлимитно, приватные до 5 человек,
  4 ГБ/репо, коммит 100 МБ; CI/CD, реестр контейнеров/пакетов, API/webhooks,
  MR-approvals, RBAC. Company — от 750 ₽/чел/мес.
- Self-hosted Community — бесплатно, неограниченно пользователей, CI/CD, LDAP/SSO.
- `gitflic-ci.yaml`: `stages`, `image`, `services` (Postgres/Redis; `docker:dind`
  для Docker-in-Docker при privileged-агенте), `cache`, `artifacts`, `rules`/
  `only`/`except`, `needs`, `extends`/anchors, `trigger`, `release`,
  `environment`, шаблоны, компоненты, планировщик конвейеров.
- MR-пайплайны включаются в настройках CI/CD проекта; конвейер результата
  слияния — отдельный флажок. Насколько «красный конвейер блокирует merge» —
  проверяем в пилоте (в GitHub это required checks).
- Агенты: Shell (UNIX), PowerShell (Windows; нужны Java 11 + Git), Docker
  (DinD), Kuber (beta). Кэш: локально на агенте, распределённый — S3 (до 5 ГБ).
- Секреты: переменные проекта с маскировкой в логах; Vault/StarVault.
- Импорт GitHub: PAT со scope `repo`; переносятся файлы, коммиты, ветки, теги
  (MR/issues/wiki — нет). Зеркала: PULL/PUSH, в облаке — обновление раз в сутки.
- Gitleaks: встроенный коннектор только в self-hosted (pre-receive hook); на
  SaaS — обычный job с образом gitleaks.
- Релизы: ключевое слово `release:` в CI + REST API/webhooks; GitFlic CLI
  вместо `gh`.

**Предварительная рекомендация:** не блокировать v0.3.0 миграцией. В спринте 21
сделать (1) диагностику GitHub billing, (2) **параллельный пилот GitFlic**
(импорт + агент + 2 job'а), (3) решение по итогам. Если паритет CI и удобство
подтвердятся — перенести origin в GitFlic в спринте 22, GitHub оставить зеркалом;
если нет — GitHub + self-hosted runner.

### S21-001: Диагностика GitHub и выбор пути — [x] (ADR принят; billing — за владельцем, CI обходится runner'ом)
- [x] Проверить причину падений: аннотация API run `41063439319` —
      «The job was not started because recent account payments have failed or
      your spending limit needs to be increased» (подтверждает KI-014)
- [ ] Поднять лимит/оплату в GitHub → Settings → Billing & plans (нужен доступ
      владельца; API billing требует scope `user` — см. `docs/CI.md` §1) и
      перезапустить run (`gh run rerun <id>`) — **не блокирует CI**: hosted-job'ы
      обойдены self-hosted runner'ом (KI-014 закрыт, `docs/CI.md` §9)
- [x] Зафиксировать варианты из §21.0 и критерии решения в `docs/CI.md` (ADR),
      включая порядок импорта приватного репо и GitFlic-пилот
- [x] **Зависит от:** — · **Оценка:** 3 ч

### S21-002: Пилот GitFlic — импорт и агент — [~] (импорт есть; живой прогон ждёт токен/агент владельца — KI-023)
- [x] Подготовить `gitflic-ci.yaml`, минимальный пилотный `ci/gitflic-pilot.yaml`
      и рунбук агентов (`docs/GITFLIC_RUNNER.md`); локально проверить все
      Docker/PowerShell-команды job'ов (frontend, lint, test, e2e, docker —
      PASS, см. `docs/CI.md` §8)
- [x] Создать компанию/проект в GitFlic (Free, ≤5 участников), импортировать
      репозиторий из GitHub (PAT `repo`), сверить ветки/теги/коммиты, `main`
      (`gitflic.ru/project/ruchating/ai-teacher_python`; расхождение: проект
      **публичный** — требуется подтверждение владельца, см. STEP-03 §4.5)
- [ ] Установить PowerShell-агент на машину проекта (Java 11 + Git, тег
      `windows-dev`) **или** Docker-агент; проверить захват задач
      (на машине Java 1.8 — нужна установка 11; registration token выдаёт
      `scripts/gitflic/setup.ps1`)
- [ ] Минимальный `gitflic-ci.yaml`: `lint` (ruff/mypy) и `test` (pytest +
      `services` postgres/redis); измерить время и стабильность
- [ ] Проверить: маскировка секретов, кэш, MR-пайплайн, поведение при падении
      job'а, ограничения Free-тарифа
- [ ] Записать результат и решение (ADR) в `docs/CI.md`; при успехе — план
      переноса origin (S21-003), при неудаче — GitHub + runner
      (ADR §9 уже фиксирует промежуточное решение: вариант A сейчас, GitFlic — цель)
- [ ] **Зависит от:** S21-001 · **Оценка:** 6 ч

### S21-003: Портирование CI на выбранную платформу — [x]
- [x] GitHub-путь (fallback): self-hosted runner + `ci-selfhosted.yml`, 6/6 job'ов
      зелёные (run 41070317162); кэш pip/pnpm — named volumes + офлайн-wheelhouse;
      required checks на GitHub Free/private недоступны (403, нужен Pro) —
      `docs/CI.md` §9–§10
- [x] GitFlic-путь: перенос 5 job'ов (`lint`, `test`, `e2e`, `frontend`,
      `security`) в `gitflic-ci.yaml`; `docker build` — на PowerShell-агенте;
      кэш и артефакты (live-проверка — в S21-002)
- [x] `pip-audit`, `gitleaks`, `pnpm audit` — как job'ы; SAST GitFlic не
      использовать (платно)
- [x] **Зависит от:** S21-002 · **Оценка:** 6 ч

### S21-004: Required checks и защита ветки — [~] (path-фильтры и скрипт готовы; автоматический гейт — KI-023)
- [~] GitHub: branch protection с 5 required checks; запрет force-push; review —
      **невозможно на Free/private (403)**; готов `scripts/ci/protect-branch.ps1`
      (6 checks + force-push, `-DryRun`/`-Verify`, exit 3 с подсказкой)
- [ ] GitFlic: правила слияния/одобрения + MR-пайплайн; **проверить на тестовом
      MR, что красный конвейер блокирует merge** (если нет — gate через
      webhook/скрипт и запись в `docs/CI.md`) — шаги описаны в `docs/CI.md` §10.3
- [x] Path-фильтры: docs-only PR не гоняет e2e/docker (GitHub `paths-ignore`,
      GitFlic `rules: changes:`)
- [ ] **Зависит от:** S21-003 · **Оценка:** 3 ч

### S21-005: Автоматизация релиза — [x] GitHub-путь проверен живьём (dry-run);
GitFlic-джоб тега готов, создание релиза — после пилота
- [x] GitHub: `workflow_dispatch` release (гейты → tag → Release) —
      `.github/workflows/release.yml` + `workflow_call` гейтов, dry-run по
      умолчанию, репетиция по тегу `v*-dryrun`; живой dry-run выполнен
      (run 41126158359: гейты 6/6 → версия 0.2.0 → заметки → DRY-RUN, тег и
      Release не создавались)
- [~] GitFlic: job с `release:` + API/CLI (notes из `RELEASES.md`), dry-run —
      job `release` (тег-пайплайн) включён, проверка notes работает локально,
      создание релиза через `release:` — после живого пилота (KI-023)
- [x] Инструкция в `docs/CI.md` (§11); при зеркалировании — порядок «тег в
      origin, зеркало догоняет»
- [x] **Зависит от:** S21-003 · **Оценка:** 3 ч

### S21-006: Документация, бейджи, KI-014 — [x]
- [x] `docs/CI.md`: платформа, jobs, required checks, кэш, перезапуск, релиз,
      зеркала/откат (§9–§13)
- [x] `docs/RULES.md` §10: обязательность зелёного CI (оговорка KI-014 снята);
      §11.20 — уроки CI
- [x] README: бейдж CI; `CHANGELOG`, `RELEASES`, `KNOWN_ISSUES`
- [x] **Зависит от:** S21-001…S21-005 · **Оценка:** 3 ч

**DoD:** на выбранной платформе красный PR не мержится (проверено тестовым PR);
5 job'ов зелёные; release dry-run; `docs/CI.md` описывает процессы и решение;
KI-014 → `Resolved` (или `Blocked` с планом, если биллинг и пилот не решаются).

**Найдено попутно (v0.2.0):** GitHub Actions job'ы падали за 2 с без шагов —
это биллинг, а не код; локальные гейты были зелёными.

---

## Спринт 22: Dependency Modernization (KI-015/016/017)

**Цель:** современные зависимости без сюрпризов для API. Закрывает KI-015,
KI-016; смягчает KI-017.

**Зависит от:** спринт 21  
**Оценка:** 2.5 дня

### S22-001: Контрактные тесты API — [x]
- [x] Снапшот `openapi.json` (`tests/contracts/openapi.json`) + тест сравнения
      (разрешены только аддитивные изменения) — `tests/contract_utils.py`,
      `scripts/snapshot_openapi.py`
- [x] Фикстуры ответов ключевых эндпоинтов: auth, tasks list/detail/submit, chat
      sessions/messages/search, classrooms/assignments, admin analytics —
      21 форма (`tests/contracts/endpoints.json`)
- [x] **Зависит от:** — · **Оценка:** 4 ч

### S22-002: `fastapi` 0.162 + `starlette` 1.x (KI-015) — [x]
- [x] Локальный wheelhouse из Docker (см. S22-005), установка в venv/образ
- [x] Апгрейд `fastapi` 0.115.5 → **0.162.0**, `starlette` 0.41.3 → **1.10.0**,
      транзитивные `annotated-doc`/`opentelemetry-api`; pydantic 2.10.1 совместим
- [x] Прогнать контрактные тесты, pytest, e2e; починить отличия — единственное
      поведенческое: 401 вместо 403 без `Authorization` (SPEC §7, тест обновлены)
- [x] `pip-audit` без `--ignore-vuln`; игноры убраны из CI
- [x] KI-015 → `Resolved`
- [x] **Зависит от:** S22-001 · **Оценка:** 8 ч

### S22-003: `pytest` 9 и dev-зависимости (KI-016) — [x]
- [x] `pytest` **9.2.0** + `pytest-asyncio` 1.4.1 / `pytest-cov` 7.1.0 /
      `pytest-env` 1.8.3; конфиг `pyproject.toml` без правок
- [~] `filterwarnings = error` — **не включён**: ~1 400 `datetime.utcnow()`
      deprecation требуют отдельной чистки (RULES §11.21 п. 8, отчёт STEP-02)
- [x] KI-016 → `Resolved`
- [x] **Зависит от:** S22-001 · **Оценка:** 4 ч

### S22-004: Dependabot и авто-мерж minor/patch — [~]
- [~] Авто-мерж minor/patch — **невозможен на GitHub Free/private** (нет
      branch protection/auto-merge, KI-023); политика и группировка описаны
      в `.github/dependabot.yml` и `docs/CI.md` §13, мерж — вручную
- [x] Проверить группировку PR (pip/npm/actions) и лимиты; устаревшие PR после
      ручного апгрейда закрыты (#18, #20, #22)
- [x] **Зависит от:** S21-002 · **Оценка:** 3 ч

### S22-005: Wheelhouse для offline-окружений (KI-017) — [x]
- [x] `scripts/wheelhouse.py`: `build --docker` (python:3.12-slim, Linux-колёса)
      в каталог/volume, `install --no-index --find-links`, `list`;
      `scripts/ci/build-wheelhouse.ps1` — обёртка для CI
- [x] Документация в `docs/GETTING_STARTED.md` §4; KI-017 → `Resolved`
      (с оговоркой, что CI-путь остаётся основным)
- [x] **Зависит от:** — · **Оценка:** 3 ч

### S22-006: Документация — [x]
- [x] `RULES.md` §11.21 «Обновление зависимостей»: контрактные тесты,
      wheelhouse, порядок апгрейда, откат (нумерация: §11.20 занят CI)
- [x] `CHANGELOG`, `ARCHITECTURE` (версии зависимостей), `CI.md` §13
- [x] **Зависит от:** S22-001…S22-005 · **Оценка:** 2 ч

**DoD:** `fastapi`/`starlette`/`pytest` обновлены; контрактные тесты и e2e зелёные;
`pip-audit` без игнора (0 high/critical без обоснования); CI required checks
проходят; KI-015/016/017 закрыты.

---

## Спринт 23: Sandbox Throughput (KI-022)

**Цель:** submit держит 5 RPS с p95 ≤ 2 с и не теряет изоляцию. Закрывает KI-022.

**Зависит от:** спринт 21 (нагрузочный job), v0.2.0  
**Оценка:** 2.5 дня

### S23-001: Батчинг тест-кейсов в одном процессе — [x]
- [x] Протокол раннера: один дочерний интерпретатор выполняет все кейсы задачи,
      результат — построчный JSON по кейсам (`_BATCH_RUNNER`), ошибки изолированы
- [x] Лимиты: память — один раз на процесс, таймаут — **на каждый кейс** в
      родителе (зависший кейс → `TimeoutError`, остальные → `SandboxError`);
      вывод обрезается по `EXECUTOR_MAX_OUTPUT`
- [x] `app/core/test_runner.py`: батчевый путь по умолчанию, последовательный —
      fallback (протокол недоступен / процесс не запустился)
- [x] **Зависит от:** — · **Оценка:** 8 ч

### S23-002: Пул warm-раннеров — [x]
- [x] Пул процессов (`app/core/runner_pool.py`, размер `EXECUTOR_POOL_SIZE`,
      по умолчанию 2), перезапуск после `EXECUTOR_POOL_MAX_TASKS` (50) задач и
      после `TimeoutError`/`MemoryError`/сбоя протокола; свежие globals на
      каждый кейс/задачу
- [x] `EXECUTOR_MAX_CONCURRENCY` согласован с пулом (батч занимает один слот);
      очередь — по-прежнему 503; пул закрывается в `lifespan`
- [x] **Зависит от:** S23-001 · **Оценка:** 6 ч

### S23-003: Нагрузочный гейт — [x]
- [x] `scripts/load_test.py --scenario submit --rps 5` → **PASS** (p95 48.9 мс
      при бюджете 2000 мс; knee не найден до 40 RPS)
- [x] Отчёт `docs/reports/sprint-23/LOAD_TEST-SUBMIT.md`: до/после, knee,
      сырые цифры `load-test.json`
- [x] CI: job `Perf smoke (submit)` — 0.5 RPS на PR; ночной
      `.github/workflows/perf-nightly.yml` — 2 RPS; `scripts/ci/perf.ps1`
- [x] **Зависит от:** S23-001, S23-002 · **Оценка:** 4 ч

### S23-004: Безопасность батча и пула — [x]
- [x] Атакующие кейсы (14) в батчевом режиме × 2 (батч/пул): `os`/`open`/
      `__class__`/`eval`/`format` — `SecurityError`/`RestrictedFeatureError`,
      побочных эффектов нет; утечки переменных между кейсами нет
- [x] Песочница не «залипает»: после `MemoryError`/`TimeoutError` следующий
      батч выполняется, процесс пула перезапускается
      (`tests/test_sandbox_batch_security.py`, 36 тестов)
- [x] **Зависит от:** S23-001, S23-002 · **Оценка:** 4 ч

### S23-005: Документация — [x]
- [x] `ARCHITECTURE`: раннер и пул (слой 5); `RULES` §11.8 п. 12–15; `SPEC`:
      лимиты, батч, пул, throughput
- [x] `KNOWN_ISSUES`: KI-022 → `Resolved`; `CHANGELOG`; `RELEASES` (спринт 23)
- [x] **Зависит от:** S23-001…S23-004 · **Оценка:** 2 ч

**DoD:** 5 RPS submit PASS по p95 (48.9 мс); тесты песочницы и атакующие кейсы
зелёные (69 + 36); перезапуск пула проверен (11 тестов); нагрузочный отчёт с
цифрами; KI-022 закрыт.

---

## Спринт 24: Sandbox Runner Isolation

**Цель:** исполнение кода — в отдельном контейнере с жёсткой изоляцией и
fallback на нативный режим. Закрывает технический долг S13-006.

**Зависит от:** спринт 23  
**Оценка:** 3 дня

### S24-001: Контейнер-раннер — [x]
- [x] Образ `ai-teacher-sandbox-runner` (python:3.12-slim + RestrictedPython +
      чистое ядро `sandbox_runtime`): non-root (65534), read-only rootfs,
      `--network none`, `--cap-drop ALL`, `no-new-privileges`, tmpfs `/tmp`,
      `--memory/--memory-swap`, `--pids-limit`
- [x] Протокол обмена (stdin/stdout JSON, тот же, что у батча), без монтирования
      исходников; `--self-check` изоляции
- [x] `EXECUTOR_MODE=container|native` (по умолчанию `native`), `EXECUTOR_IMAGE`
- [x] **Зависит от:** S23-001 · **Оценка:** 8 ч

### S24-002: Fallback и совместимость — [x]
- [x] Docker недоступен/обрза нет → нативный режим + warning (один раз) и
      счётчик `fallbacks`; Windows dev остаётся на Job Object/RLIMIT_AS
- [x] Сборка образа по требованию (`scripts/ci/build-sandbox-image.ps1`), проверка
      в CI (job `Docker build`); ресурсы — `EXECUTOR_MEMORY_LIMIT`
- [x] **Зависит от:** S24-001 · **Оценка:** 4 ч

### S24-003: Тесты изоляции — [x]
- [x] Контейнерный режим: сеть недоступна, rootfs read-only, tmpfs пишется,
      `CapEff=0`, uid 65534 (self-check); 14 атакующих векторов — зелёные
- [x] Проверка read-only FS и tmpfs-политики; тест на память/таймаут и
      восстановление после них
- [x] **Зависит от:** S24-001 · **Оценка:** 5 ч

### S24-004: Метрики и лимиты — [x]
- [x] Время старта контейнера в метриках (`start_ms_avg/last`), `runs`,
      `timeouts`, `errors`, `fallbacks`; пул контейнеров — отложен (см.
      отчёт SPRINT-24 §5)
- [x] Метрики — заглушка логом/снимком до `/metrics` в спринте 25
- [x] **Зависит от:** S24-001 · **Оценка:** 4 ч

### S24-005: Документация — [x]
- [x] `ARCHITECTURE` (слой 6), `RULES` §11.8 п. 16–18, `SPEC` (режим),
      `GETTING_STARTED`/`DESIGN_ADMIN_AND_OPS` — в отчёте SPRINT-24
- [x] `CHANGELOG`, `RELEASES` (спринт 24), `TODO`
- [x] **Зависит от:** S24-001…S24-004 · **Оценка:** 2 ч

**DoD:** контейнерный режим проходит атакующие кейсы и лимиты (21 тест);
fallback документирован; влияние на p95 submit зафиксировано (следствие: режим
включается флагом); выбор режима — флагом `EXECUTOR_MODE`.
## Спринт 25: Observability & Audit Log

**Цель:** видно, что происходит с сервисом и кто что сделал. Для эксплуатации,
не для «красоты».

**Зависит от:** спринт 21  
**Оценка:** 2 дня

### S25-001: Request-ID и корреляция логов — [x]
- [x] Middleware: `X-Request-ID` (входящий или uuid4), `request_id` в structlog
      context, заголовок в ответе; `current_request_id()` для сервисов
- [x] **Зависит от:** — · **Оценка:** 3 ч

### S25-002: Prometheus `/metrics` — [x]
- [x] `prometheus_client`: HTTP (route/method/status/latency), LLM (gauge из
      счётчиков), cache, sandbox (runs/timeouts/длительность), DB pool
- [x] Отдельный эндпоинт без авторизации для внутренней сети; nginx → 404
- [x] **Зависит от:** S25-001 · **Оценка:** 5 ч

### S25-003: Liveness/Readiness — [x]
- [x] `/health/live` и `/health/ready` (БД/Redis/LLM-конфиг); `/api/v1/health`
      сохранён; compose healthcheck → readiness
- [x] **Зависит от:** — · **Оценка:** 2 ч

### S25-004: Audit log действий teacher/admin — [x]
- [x] Таблица `audit_log` (актор, действие, сущность, payload-сводка, IP, время),
      миграция 011; записи: роли, задачи, классы, назначения, удаление
- [x] `GET /api/v1/admin/audit` (admin, пагинация/фильтры)
- [x] **Зависит от:** S25-001 · **Оценка:** 5 ч

### S25-005: Документация и дашборд-гайд — [x]
- [x] `DESIGN_ADMIN_AND_OPS` §10: метрики, алерты, логи, аудит; `MANUAL_TESTING_GUIDE`
- [x] **Зависит от:** S25-001…S25-004 · **Оценка:** 3 ч

**DoD:** `/metrics` отдаёт метрики; request_id в логах и ответе; readiness
корректно отражает зависимости; audit log пишется и читается админом.

## Спринт 26: Export, Retention & Privacy

**Цель:** данные можно выгрузить, ограничить по сроку и удалить по запросу.

**Зависит от:** спринт 25  
**Оценка:** 2 дня

### S26-001: Экспорт аналитики CSV/JSON — [x]
- [x] `GET /admin/analytics/export?format=csv|json` — users/tasks/attempts/activity;
      стриминг (серверный курсор), лимит `EXPORT_MAX_ROWS`, аудит скачивания
- [x] **Зависит от:** — · **Оценка:** 4 ч

### S26-002: Отчёт класса — [~] (API готов, UI-кнопка — отдельным шагом)
- [x] `GET /classrooms/{id}/report?format=csv` — матрица прогресса, overdue, итоги
- [ ] UI-кнопка «Скачать отчёт» на странице класса
- [x] **Зависит от:** S16 (классы) · **Оценка:** 4 ч

### S26-003: Retention-политика — [x]
- [x] Конфиг `RETENTION_*_DAYS` (chat_messages, code_executions, notifications,
      audit_log); `scripts/apply_retention.py` (`--dry-run`, `--only`, батчи)
- [x] Cron/ручной запуск задокументирован; лог `retention_applied` с числом строк
- [x] **Зависит от:** — · **Оценка:** 4 ч

### S26-004: Удаление аккаунта и ПДн — [x]
- [x] `DELETE /auth/me` (пароль обязателен): анонимизация, `is_active=false`
      (миграция 012), аудит `user.self_deleted`
- [x] `docs/PRIVACY.md`: данные, сроки, экспорт, удаление; ссылка в USER_GUIDE
- [x] **Зависит от:** S26-003 · **Оценка:** 4 ч

### S26-005: Документация — [x]
- [x] `SPEC` §16, `DESIGN_ADMIN_AND_OPS` §11, RULES §11.23, `CHANGELOG`
- [x] **Зависит от:** S26-001…S26-004 · **Оценка:** 2 ч

**DoD:** экспорт аналитики и класса работает (UI-кнопка отчёта — остаток);
retention dry-run и применение; удаление аккаунта анонимизирует данные;
политика ПДн описана.

## Спринт 27: RAG v2 & Search UX

**Цель:** поиск по истории чата становится полезным: backfill, порог
релевантности, UI.

**Зависит от:** спринт 22 (апгрейды), v0.2.0  
**Оценка:** 2 дня

### S27-001: Backfill эмбеддингов — [x]
- [x] `scripts/backfill_embeddings.py` + `app/services/backfill.py`: батчи, лимит,
      `--sleep`, `--dry-run`, идемпотентность, продолжение после ошибок
- [x] **Зависит от:** — · **Оценка:** 4 ч

### S27-002: Порог релевантности и качество — [x]
- [x] `RAG_MIN_SCORE` (cosine-порог); пустая выдача → ILIKE-фолбэк
- [x] Фикстуры `tests/fixtures/rag_queries.json` + тест precision@k
- [x] **Зависит от:** S27-001 · **Оценка:** 4 ч

### S27-003: UI поиска в чате — [x]
- [x] Панель `ChatSearchPanel` на `ChatPage`: результаты с подсветкой, переход
      к сессии; i18n ru/en; a11y (`aria-live`, `<mark>`)
- [x] Frontend-тесты (4) + e2e-сценарий в `e2e/chat.spec.ts`
- [x] **Зависит от:** S27-002 · **Оценка:** 6 ч

### S27-004: Документация — [x]
- [x] `SPEC` §17, `USER_GUIDE` (как искать), `ARCHITECTURE`, `RULES` §11.24
- [x] **Зависит от:** S27-001…S27-003 · **Оценка:** 3 ч

**DoD:** backfill работает идемпотентно; поиск в UI с порогом и фолбэком;
e2e-сценарий зелёный.

## Спринт 28: Teacher & Classroom v3

**Цель:** учитель экономит время: массовые действия, журнал оценок, уведомления.

**Зависит от:** спринт 26  
**Оценка:** 2.5 дня

### S28-001: Массовые назначения — [x]
- [x] `POST /classrooms/{id}/assignments/bulk` `{task_ids[]}`; идемпотентность,
      отчёт `{created, skipped, unknown}`, уведомления только по новым
- [ ] UI: мультивыбор задач и классов (остаток)
- [x] **Зависит от:** — · **Оценка:** 6 ч

### S28-002: Шаблоны назначений — [x]
- [x] Таблица `assignment_templates` (миграция 013), CRUD
      `/teacher/assignment-templates`, применение к классу
- [x] **Зависит от:** S28-001 · **Оценка:** 4 ч

### S28-003: Журнал оценок — [x]
- [x] `GET /classrooms/{id}/gradebook` (status/attempts/completed_at/overdue) +
      `/gradebook/csv` (формат S26-002)
- [ ] UI-страница `/classrooms/:id/gradebook` (остаток)
- [x] **Зависит от:** S26-002 · **Оценка:** 6 ч

### S28-004: Email-уведомления (опционально) — [x]
- [x] `NOTIFICATIONS_EMAIL_ENABLED` + SMTP-конфиг; dev — логирование;
      назначение и напоминание о дедлайне (`scripts/notify_deadlines.py`)
- [x] Ошибка SMTP не ломает API; тест с фейковым отправителем
- [x] **Зависит от:** — · **Оценка:** 6 ч

### S28-005: Документация — [x]
- [x] `USER_GUIDE` (учитель), `SPEC` §18, `RULES` §11.25, `CHANGELOG`
- [x] **Зависит от:** S28-001…S28-004 · **Оценка:** 2 ч

**DoD:** массовые назначения и шаблоны работают; журнал оценок с экспортом;
email включается флагом и не ломает API (UI-часть — остаток).

## Спринт 29: UX, A11y & i18n Completion

**Цель:** закрыть остатки v0.2.0: мобильные таблицы, локализация, автоматическая
проверка контраста.

**Зависит от:** спринт 22 (frontend-апгрейды)  
**Оценка:** 2 дня

### S29-001: Карточный вид таблиц на мобильных — [x]
- [x] `Table`/`Tr`/`Td`/`Th` → карточки `<sm` для админки/учителя/классов;
      без горизонтального скролла; тест на 375 px (e2e) + unit
- [x] **Зависит от:** — · **Оценка:** 4 ч

### S29-002: Аудит локализации — [x]
- [x] Убраны RU-fallback в `api.ts`/`auth.ts`/`chatSocket.ts`/сторах (`errors.*`)
- [x] `scripts/check-i18n.mjs` в CI: кириллица вне локалей + паритет ключей
- [x] **Зависит от:** — · **Оценка:** 4 ч

### S29-003: Авто-проверка контраста — [x]
- [x] Playwright + `axe-core` на ключевых страницах light/dark: 0 нарушений
- [x] **Зависит от:** — · **Оценка:** 4 ч

### S29-004: E2E a11y/мобильные сценарии — [x]
- [x] skip-link, мобильное меню, таблицы-карточки на 375 px
- [x] **Зависит от:** S29-001, S29-003 · **Оценка:** 4 ч

### S29-005: Документация — [x]
- [x] `MANUAL_TESTING_GUIDE` §17, `SPEC` §19, `RULES` §11.26, `CHANGELOG`
- [x] **Зависит от:** S29-001…S29-004 · **Оценка:** 2 ч

**DoD:** таблицы-карточки на мобильных; 0 RU-fallback в UI; axe-контраст 0
нарушений; e2e a11y зелёные.

## Спринт 30: Release v0.3.0

**Цель:** стабильный релиз с руководством по апгрейду.

**Зависит от:** спринты 21–29  
**Оценка:** 2 дня

### S30-001: Руководство по апгрейду v0.2.0 → v0.3.0 — [x]
- [x] `docs/UPGRADE.md`: миграции 011–013, новые ENV, runner/метрики, откат
- [x] **Зависит от:** все спринты · **Оценка:** 4 ч

### S30-002: Полные гейты — [x]
- [x] backend: ruff/mypy/pytest/alembic check; frontend: typecheck/lint/test/build/
      offline; e2e; docker (в CI)
- [x] `pip-audit` строгий, без необоснованных игноров
- [x] **Зависит от:** S30-001 · **Оценка:** 4 ч

### S30-003: Документация v0.3.0 — [x]
- [x] `SPEC`, `ARCHITECTURE`, `DESIGN_ADMIN_AND_OPS`, `USER_GUIDE`,
      `MANUAL_TESTING_GUIDE`, `RULES`, `CHANGELOG [0.3.0]`, `RELEASES`,
      `KNOWN_ISSUES` (KI-024/025), `README`
- [x] **Зависит от:** S30-002 · **Оценка:** 5 ч

### S30-004: Версия, тег, релиз — [x]
- [x] Версия `0.3.0` в `pyproject.toml`/`package.json`/`config.py`
- [x] PR → merge → тег `v0.3.0` → GitHub Release (`release.yml`)
- [x] **Зависит от:** S30-003 · **Оценка:** 2 ч

**DoD:** обновление с v0.2.0 описано и проверено; все гейты зелёные; CI зелёный;
тег `v0.3.0` и GitHub Release созданы автоматизированно.

