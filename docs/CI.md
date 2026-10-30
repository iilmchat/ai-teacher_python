# CI.md — CI-платформа: диагностика, варианты и решение (S21)

> Документ спринта 21 (v0.3.0). Закрывает `KI-014` (GitHub Actions не запускает
> job'ы) и фиксирует выбор CI-платформы. Решение принимается в два шага:
> диагностика GitHub + пилот GitFlic (S21-002), затем ADR-итог.
>
> Обновлено: 2026-10-30. Статус: **пилот GitFlic идёт**, окончательное решение —
> после S21-002 (см. §5 «Критерии»).

---

## 1. Контекст и проверенные факты

**Симптом.** Все job'ы GitHub Actions завершаются за 0–2 с без выполнения шагов.
Пример: run `41063439319` (push, 2026-10-30T13:27:48Z) — `Lint (Backend)`,
`Security`, `Frontend` = failure, `Test (Backend)`, `Docker Build`,
`E2E (Playwright)` = skipped.

**Причина (подтверждена аннотацией API, а не только сообщением UI):**

```text
GET /repos/iilmchat/ai-teacher_python/check-runs/<job_id>/annotations
→ "The job was not started because recent account payments have failed or your
   spending limit needs to be increased. Please check the 'Billing & plans'
   section in your settings"
```

Это ровно `KI-014`: код, workflow и локальные гейты ни при чём (ruff/mypy/pytest,
frontend, e2e, docker — зелёные локально, см. `docs/reports/sprint-20/`).

**Ограничение доступа к биллингу из CLI.** Текущий токен `gh` имеет scopes
`gist, read:org, repo, workflow` — без `user`, поэтому:

```text
gh api /users/iilmchat/settings/billing/actions
→ 404 "This API operation needs the user scope"
```

Прочитать billing можно так:

- веб: GitHub → Settings → **Billing & plans** → Actions (минуты/лимит расходов);
- CLI (интерактивно, потребуется браузер): `gh auth refresh -h github.com -s user`,
  затем `gh api /users/iilmchat/settings/billing/actions`.

**Факт про наш репозиторий.** `iilmchat/ai-teacher_python` — **приватный**
(`visibility: PRIVATE`). Значит для импорта в GitFlic нужен GitHub-токен
(см. §6): без него GitFlic не вытянет приватный репозиторий.

**Что уже работает локально (не заменяет CI, но снимает риск «слепой» разработки):**
backend 341 passed + 1 skipped, ruff/mypy 0, `alembic check`; frontend 80/80,
build 78.71 kB gzip, `test:offline`; e2e 12/12; docker prod smoke 4/4 healthy.

---

## 2. Варианты CI-платформы

| Вариант | Стоимость | Плюсы | Минусы |
|---------|-----------|-------|--------|
| **A. GitHub + self-hosted runner** на машине проекта | 0 ₽ | нулевая миграция; PR checks, `gh`-скрипты, Releases остаются; за 1–2 часа разворачивается | зависимость от GitHub (биллинг/санкции); машина должна быть включена; GitHub Actions всё ещё требует минимальных минут для public/hosted — но self-hosted job'ы не тарифицируются |
| **B. GitFlic SaaS + свой агент** | 0 ₽ (≤5 человек, приватный репо 4 ГБ) | RU-хостинг; CI/CD в free-плане; GitLab-подобный `gitflic-ci.yaml` (`services`, DinD, cache, artifacts, MR-pipelines, release); импорт с GitHub; зеркала PULL/PUSH; реестр контейнеров/пакетов | облачные агенты по умолчанию выключены → нужен свой агент; зеркало в облаке раз в сутки и по разрешению поддержки; MR/issues/wiki не переносятся; Gitleaks-интеграция только в self-hosted; SAST/merge trains/аудит — платно |
| **C. GitFlic Self-hosted Community** | 0 ₽ + сервер (1 ядро/2 ГБ/10 ГБ, Java 11, PostgreSQL 11+, Redis 6+) | полный контроль и RU; unlimited users; CI/CD, агенты, LDAP/SSO OIDC | эксплуатация сервера, обновления, бэкапы — на нас |
| **D. GitLab CE self-hosted** | сервер | зрелый CI, полный перенос MR/issues (CE) | тяжёлая эксплуатация; избыточно для одного проекта |
| **E. Только локальные гейты** | 0 ₽ | ничего не нужно | нет required checks → регресс в `main`; не закрывает KI-014 |

Стоимость GitFlic (проверено на 2026-10-30): SaaS Free — публичные репо
безлимитно, приватные до 5 человек, 4 ГБ/репо, CI/CD включён; Company — от
750 ₽/чел/мес; Self-hosted Community — 0 ₽, Pro — от 243 000 ₽/год.

---

## 3. Решение (шаг 1): пилот GitFlic при сохранении GitHub как резерва

1. **Не блокировать v0.3.0 миграцией.** Пока CI не работает, гейты — локальные
   (RULES §10) + ручной чек-лист; это временно.
2. **Параллельный пилот GitFlic (S21-002):** импорт репозитория, PowerShell-
   или Docker-агент на машине проекта, минимальный `gitflic-ci.yaml` из 2 job'ов
   (`lint`, `test` с `services` Postgres/Redis), проверка MR-пайплайна и секретов.
3. **Fallback (вариант A):** self-hosted runner GitHub разворачивается, если
   пилот не даст паритета за 2 рабочих дня.
4. **Перенос origin в GitFlic** — только после выполнения критериев §5 и
   отдельным решением; до этого GitHub остаётся origin, GitFlic — пилот/зеркало.

**Почему так:** GitFlic закрывает стратегический риск (RU-хостинг, реестр
отечественного ПО, независимость от биллинга GitHub) и стоит 0 ₽ на нашем
масштабе, но требует своей инфраструктуры (агент) и имеет ограничения
(зеркала, MR-история, экосистема). Полный переезд без пилота — риск для релиза.

---

## 4. Как выглядит CI на GitFlic (план порта)

Файл `gitflic-ci.yaml` (в корне; путь настраивается в CI/CD проекта).
Соответствие job'ов:

| GitHub job | GitFlic job | Runner | Образ/сервисы |
|------------|-------------|--------|---------------|
| `lint` | `lint` | Docker-агент (Linux) | `python:3.12-slim` |
| `test` | `test` | Docker-агент | `python:3.12-slim` + `services: pgvector/pgvector:pg17, redis:7-alpine` |
| `frontend` | `frontend` | Docker-агент | `node:22-alpine` |
| `security` | `security-backend`, `security-frontend`, `gitleaks` | Docker-агент | `python:3.12-slim`, `node:22-alpine`, `zricethezav/gitleaks` |
| `e2e` | `e2e` | **PowerShell-агент** (Windows, `tags: [windows-dev]`) | host: Node/pnpm/Playwright/Docker Desktop |
| `docker` | `docker` | PowerShell-агент или DinD | host Docker / `docker:dind` |
| release (ручной) | `release` | Docker-агент | + `release:` keyword, gate по `CI_COMMIT_TAG` |

Особенности GitFlic, которые учтены в конфиге:

- нет GitHub-подобных `uses:`/`runs-on` — только `image` + `tags`;
- у `services` нет healthcheck-опций → в `before_script` ждём готовности
  `pg_isready`/`redis-cli ping` (retry-цикл);
- MR-пайплайн включается флажком в настройках CI/CD проекта; переменные
  `CI_PIPELINE_TYPE`/`CI_MERGE_REQUEST_*`;
- секреты — переменные проекта с маской (в файле только имена);
- кэш — локальный на агенте (или S3), ключ по lock-файлам;
- подпись/артефакты — `artifacts:paths`, `expire_in`;
- релизы — `release:` + GitFlic API/CLI (`gcli`), а не `gh`.

Руководство по установке агента и настройке проекта — `docs/GITFLIC_RUNNER.md`.

---

## 5. Критерии решения (после S21-002)

Пилот считается успешным, только если **всё** выполнено:

- [ ] репозиторий импортирован: ветки/теги/коммиты совпадают с GitHub `main`;
- [ ] агент забирает задачи, `lint` и `test` зелёные на нашем коде;
- [ ] `test` видит Postgres/Redis через `services` (без ручных контейнеров);
- [ ] секреты маскируются в логах, `.env` не попадает в репозиторий;
- [ ] MR-пайплайн создаётся автоматически и **красный пайплайн блокирует merge**
      (или есть рабочий gate через webhook/API из S21-004);
- [ ] время PR-пайплайна ≤ 10 минут (5 job'ов, кэш);
- [ ] e2e на PowerShell-агенте стабилен (2 прогона подряд);
- [ ] release dry-run: tag → job `release` → Release в GitFlic (или
      документированный план переноса релизов).

Если хотя бы один пункт не выполняется и не имеет внятного workaround — выбираем
вариант A (GitHub self-hosted runner), а GitFlic остаётся зеркалом/заделом на
будущее (KI остаётся `Blocked` с планом).

---

## 6. Импорт приватного репозитория в GitFlic (для Lead/владельца)

Нужен **GitHub Personal Access Token** (PAT), потому что репозиторий приватный:

1. GitHub → Settings → Developer settings → **Personal access tokens**:
   - *Fine-grained* (рекомендуется): Repository access = только
     `iilmchat/ai-teacher_python`; Permissions → Repository permissions →
     **Contents: Read-only**; срок — 7–30 дней.
   - или *Tokens (classic)*: scope **`repo`** (полный доступ к приватным репо).
2. GitFlic → «+» → **Импорт проекта**:
   - URL: `https://github.com/iilmchat/ai-teacher_python.git`
   - Логин: `iilmchat`
   - Токен: PAT из п.1.
3. Проверить: ветка `main`, теги (`v0.2.0`), история коммитов, `.github/` (не
   исполняется, но пусть будет), затем включить CI/CD и указать
   `gitflic-ci.yaml`.
4. Пат **отозвать** сразу после импорта (он больше не нужен).
5. Зеркало GitHub↔GitFlic (опционально): в облаке создание зеркала требует
   прав — запросить в поддержке GitFlic; обновление раз в сутки.

> PAT — это пароль-заменитель для автоматизации; не коммитить, не пересылать
> в чатах, хранить в менеджере секретов. Для GitFlic-агента понадобится
> отдельный токен агента (его выдаёт GitFlic при регистрации агента).

---

## 7. Дальнейшие шаги (S21-003…S21-006)

1. **S21-003:** порт 5 job'ов, кэш pip/pnpm/playwright, артефакты; при выборе
   варианта A — self-hosted runner GitHub.
2. **S21-004:** required checks / MR-gate, path-фильтры (docs-only), запрет
   force-push.
3. **S21-005:** release-workflow (`workflow_dispatch` для GitHub или `release:`
   job для GitFlic), dry-run.
4. **S21-006:** бейджи, RULES §10 без оговорки KI-014, отчёт
   `docs/reports/sprint-21/SPRINT-21.md`, статус KI-014.

---

## 8. Ссылки

- Тарифы GitFlic: <https://gitflic.ru/price>
- Справочник `gitflic-ci.yaml`: <https://docs.gitflic.ru/latest/en/cicd/gitflic-ci-yaml/>
- Конвейеры и MR-пайплайны: <https://docs.gitflic.ru/latest/en/cicd/pipeline/>
- Агенты (runner): <https://docs.gitflic.ru/latest/en/setup/runner/agent_types/>
- Импорт проекта: <https://docs.gitflic.ru/latest/en/project/import_base/>
- Зеркалирование: <https://docs.gitflic.ru/latest/en/project/mirror/>
- Гайд по переносу с GitHub/GitLab: <https://habr.com/ru/companies/astralinux/articles/1042676/>
- GitHub Actions billing API: <https://docs.github.com/rest/billing/billing>
