# SPRINT-21.md — CI & Quality Gates (v0.3.0)

**Период:** 2026-10-30  
**Задачи:** S21-001…S21-006  
**Статус:** ✅ CI снова работает (6/6 job'ов, self-hosted runner);
⚠️ автоматический merge-gate не включён — `KI-023` (GitHub Free/private +
доступ владельца к GitFlic)

---

## 1. Файлы (+/-)

```
+ .github/workflows/ci-selfhosted.yml            — fallback CI на self-hosted
                                                   runner'е (6 job'ов), workflow_call,
                                                   paths-ignore, named volumes
+ .github/workflows/release.yml                  — гейты → тег → GitHub Release
+ ci/gitflic-pilot.yaml                          — пилотный пайплайн GitFlic
+ gitflic-ci.yaml                                — полный порт CI на GitFlic
+ docs/CI.md                                     — ADR, гейты, релиз, эксплуатация
+ docs/GITFLIC_RUNNER.md                         — рунбук агентов и настроек проекта
+ docs/reports/sprint-21/STEP-01_CI_DIAGNOSTICS.md
+ docs/reports/sprint-21/STEP-02_PILOT_HARDENING.md
+ docs/reports/sprint-21/STEP-03_SELFHOSTED_FALLBACK.md
+ docs/reports/sprint-21/STEP-04_QUALITY_GATES_RELEASE.md
+ docs/reports/sprint-21/SPRINT-21.md            — этот отчёт
+ scripts/ci/backend-lint.sh                     — ruff+mypy в python:3.12-slim
+ scripts/ci/backend-test.sh                     — alembic + pytest с Postgres/Redis
+ scripts/ci/frontend.sh                         — typecheck/lint/test/build
+ scripts/ci/security-backend.sh                 — pip-audit (wheelhouse/зеркало/OSV)
+ scripts/ci/security-frontend.sh                — pnpm audit --audit-level=high
+ scripts/ci/e2e.ps1                             — Playwright e2e на Windows-хосте
+ scripts/ci/docker.ps1                          — docker build + prod-compose config
+ scripts/ci/install-python-deps.sh              — wheelhouse → PyPI → зеркала
+ scripts/ci/build-wheelhouse.ps1                — офлайн-wheelhouse (Linux-колёса)
+ scripts/ci/protect-branch.ps1                  — required checks + force-push
+ scripts/gitflic/setup.ps1                      — переменные, агент, конвейер (API)
+ backend/scripts/release_notes.py               — заметки из docs/RELEASES.md
+ backend/scripts/check_version.py               — версия в трёх источниках
+ backend/tests/test_release_tools.py            — 13 тестов
~ .github/workflows/ci.yml                       — ручной режим (KI-014), paths-ignore
~ .gitattributes                                 — LF для .sh/.yaml, CRLF для .ps1
~ docs/RULES.md                                  — §2.3, §5.1, §10, §11.19, §11.20
~ docs/RELEASES.md, docs/CHANGELOG.md            — спринт 21 / [Unreleased]
~ docs/KNOWN_ISSUES.md                           — KI-014 → Resolved, KI-023
~ docs/README.md                                 — ссылка на docs/CI.md
~ TODO_V0.3.md                                   — статусы S21-001…S21-006
~ README.md                                      — бейдж CI
```

Итого: 20 новых файлов, 9 изменённых; кода — ~1 700 строк (CI-конфиги, скрипты,
тесты), остальное — документация.

---

## 2. Покрытие

- **`backend/tests/test_release_tools.py` — 13 тестов:**
  - `release_notes`: приоритет заголовка «Релиз» над «Этап … — релиз», границы
    раздела (не включает следующий), отсутствие версии → `None`/`LookupError`
    со списком доступных релизов, защита от совпадения префикса (`0.2.01` ≠
    `0.2.0`), реальный `docs/RELEASES.md` содержит заметки `v0.2.0`;
  - `check_version`: чтение трёх источников, обнаружение расхождения,
    `--expected`, `--strict`, код 2 при битом `config.py`, инвариант «версии в
    репозитории согласованы»;
  - CLI: `--output`, `--list`, отсутствующий файл журнала (exit 2).
- **Непокрытое (осознанно):** YAML-workflow'ы и PowerShell-скрипты не
  юнит-тестируются — они проверяются живым прогоном CI (`lint`, `test`,
  `frontend`, `security`, `e2e`, `docker`) и `-DryRun`/`-Verify` для
  `protect-branch.ps1`; `release.yml` — прогоном dry-run (после мержа).
- **Тестовый job теперь копирует `docs/RELEASES.md` и `frontend/package.json`**
  в рабочую копию контейнера — иначе тесты инструментов релиза не находят
  файлы (найдено локальным прогоном).

---

## 3. Результаты

| Проверка | Результат |
|----------|-----------|
| `ruff check app tests scripts` (ruff 0.8.1) | **0 ошибок** |
| `mypy app --config-file ../pyproject.toml` (strict) | **0 ошибок** |
| `pytest -q` (контейнер + pgvector/redis, как в CI) | **354 passed, 1 skipped** (97 с) |
| Frontend: typecheck / lint / test / build | **80/80**, build **78.71 kB gzip** |
| E2E Playwright | **12/12** |
| CI `CI (self-hosted fallback)` | **6/6 success** (см. §4) |
| `pip-audit` (wheelhouse/зеркало + OSV) | «No known vulnerabilities found, 16 ignored», exit 0 |
| `pnpm audit --audit-level=high` | 0 |
| `alembic upgrade head` + `alembic check` | OK, миграции до `010` |

Build: 0 ошибок / 0 предупреждений (typecheck+build). Tests: 354/355
(1 skip — Windows-only проверка).

---

## 4. Smoke

Ручной сценарий проверки CI (выполнялся по ходу спринта):

1. `gh api repos/iilmchat/ai-teacher_python/actions/runners` → runner
   `ai-teacher-win` `status: online`.
2. Push в `sprint/21-ci` → PR #27 → workflow `CI (self-hosted fallback)`
   запускается на PR.
3. Все 6 job'ов зелёные: `Lint (backend)` (ruff+mypy в контейнере),
   `Test (backend)` (alembic + 354 passed), `Frontend` (80/80 + build),
   `Security` (pip-audit, pnpm audit, gitleaks), `E2E (Playwright)` (12/12),
   `Docker build` (оба образа + compose config).
4. Docs-only PR (проверка path-фильтров): изменение только `docs/**` не
   запускает workflow (условие `paths-ignore`), PR с кодом — запускает.
5. `pwsh scripts/ci/protect-branch.ps1 -Verify` → 403 «Upgrade to GitHub Pro…»
   (ожидаемо на Free/private; exit 1), `-DryRun` печатает payload с 6 checks.
6. Локальная репетиция релиза: `check_version.py` → OK (0.2.0 во всех файлах),
   `release_notes.py --version 0.2.0` → заметки из журнала,
   `release_notes.py --version 9.9.9` → exit 1 + список доступных релизов.

---

## 5. Что не так

1. **Автоматический merge-gate отсутствует (KI-023).** GitHub Free/private не
   даёт branch protection (403), GitFlic-пилот ждёт access token владельца и
   агента (Java 11). Пока действует правило RULES §10: мерж только при зелёном
   `CI (self-hosted fallback)` — проверка глазами.
2. **PyPI с машины недоступен (KI-017) — усилено.** `pip install` в
   контейнере job'а залипал на 20+ минут (TLS-таймауты к pypi.org), из-за чего
   первые прогоны падали по инфраструктуре, а не по коду. Решение: офлайн-
   wheelhouse (69 МБ, 71 колесо, Linux) в named volume + fallback на зеркала;
   job'ы больше не зависят от pypi.org. Побочный эффект: `security-backend`
   переключается на advisory-сервис OSV, когда pypi.org не отвечает (набор
   находок совпал: 16 ignored).
3. **Живой пилот GitFlic не выполнен** (S21-002): импорт проекта есть, но
   настройка CI/CD, агент и MR-пайплайн требуют доступа владельца. Локально
   прогнаны команды всех job'ов; `services`, маскировка и поведение MR на
   платформе не подтверждены.
4. **Release dry-run на GitHub ещё не запускался живьём:** `workflow_dispatch`
   требует наличия файла в `default`-ветке, а реальный тег мы не создаём до
   релиза. Репетиция запланирована сразу после мержа спринта: тег
   `v0.2.0-dryrun` (всегда dry-run) или `gh workflow run release.yml`.
5. **Hosted `ci.yml` отключён от PR** (ручной режим): иначе каждый PR висит с
   красным workflow из-за биллинга. Возврат — одна правка `on:` после оплаты
   (KI-014, `docs/CI.md` §9).
6. **Публичность GitFlic-проекта.** Импорт создан как **публичный** проект
   (`gitflic.ru/project/ruchating/ai-teacher_python`) — это требует
   подтверждения владельца: код проекта был приватным на GitHub. Отмечено в
   STEP-03 §4.5; при необходимости проект переводится в приватный до пилота.
7. **Лишние артефакты локальной проверки.** `backend/venv` (Python 3.12, из
   wheelhouse) создан для e2e и в git не попадает (`venv/` в `.gitignore`);
   named volumes (`ai-teacher-*`) — локальная инфраструктура runner'а.

---

## 6. Новые KI

- **KI-023 · Open · High · CI · merge-gate не обеспечен** — GitHub Free/private
  не даёт required checks, GitFlic-пилот ждёт доступ владельца. Workaround:
  RULES §10 (мерж только при зелёном CI, проверка глазами); план — токен/агент
  GitFlic → MR-гейт, либо GitHub Pro + `scripts/ci/protect-branch.ps1`.
- **KI-014 → Resolved:** CI работает на self-hosted runner'е (6/6), hosted-минуты
  остаются за владельцем (workflow в ручном режиме).

Других новых проблем нет; KI-015/KI-016/KI-017/KI-018/KI-022 — без изменений
(у KI-017 обновлён раздел про CI-путь).

---

## 7. Обоснование

1. **Сначала процесс, потом риск.** Спринт 21 не трогал продуктовый код: весь
   дифф — CI, скрипты и документация. Это позволяет начать спринт 22
   (апгрейды `fastapi`/`starlette`) с уже зелёными гейтами.
2. **Вариант A (self-hosted runner) как немедленное решение, GitFlic — цель.**
   Гипотеза «переехать на GitFlic прямо сейчас» не проверена (нет доступа), а
   релиз блокировать нельзя. Self-hosted runner даёт зелёный CI сегодня, не
   расходует минуты GitHub и использует уже проверенные Docker-команды; GitFlic
   остаётся стратегическим путём (§9 `docs/CI.md`).
3. **Гейты переиспользуются (`workflow_call`), а не дублируются.** Релиз
   обязан проверять то же, что PR; копия команд в двух файлах неизбежно
   разъедется — как уже случилось с unpinned ruff/mypy в старом CI.
4. **Офлайн-first для зависимостей.** Сеть до PyPI — внешняя и нестабильная
   (KI-017); CI должен падать по коду, а не по удаче с TLS. Wheelhouse +
   зеркала + кэши — воспроизводимо и переносимо на GitFlic/облачный агент.
5. **Release: dry-run по умолчанию, версия в трёх файлах, заметки из журнала.**
   Релиз — необратимое действие; проверки версии (`--strict`) и заметок
   выполняются до тега, повторный номер тега запрещён. Заметки ведутся по
   RULES §2.4 — дублировать их генерацией из коммитов нет смысла.
6. **Честная фиксация ограничений.** Вместо «CI зелёный, значит всё готово» —
   отдельный KI-023 на merge-gate, обновлённый KI-017 и ручной режим hosted-CI:
   следующий спринт должен видеть реальную картину.
