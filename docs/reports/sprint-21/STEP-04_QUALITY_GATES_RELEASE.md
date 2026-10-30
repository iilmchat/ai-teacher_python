# Шаг 04/спринт 21: гейты, path-фильтры и автоматизация релиза

**Дата:** 2026-10-30  
**Спринт:** 21 (v0.3.0)  
**Задачи:** S21-004 (гейты), S21-005 (релиз), S21-006 (документация);
плюс hardening S21-003 под нестабильный PyPI (KI-017)  
**Статус:** ✅ сделано всё, что не требует доступа владельца к GitFlic;
автоматический merge-gate — `KI-023`

---

## 1. Что сделано

1. **Релиз одной командой** — `.github/workflows/release.yml`: гейты
   (`uses: ./.github/workflows/ci-selfhosted.yml`) → сверка версии → заметки →
   (dry-run | тег + `gh release create`). `workflow_call` добавлен в
   `ci-selfhosted.yml`, поэтому 6 job'ов не дублируются.
2. **Dry-run по умолчанию** и соглашение о тегах: `workflow_dispatch` без
   `dry_run=false` ничего не создаёт; тег `v*-dryrun` запускает репетицию и не
   порождает второй прогон гейтов (реальный тег создаёт workflow сам).
3. **Версия — в трёх файлах, заметки — из журнала:**
   `backend/scripts/check_version.py` (pyproject.toml / frontend/package.json /
   backend/app/config.py; `--strict` для реального релиза) и
   `backend/scripts/release_notes.py` (раздел «## Релиз vX.Y.Z» из
   `docs/RELEASES.md`; приоритет заголовку «Релиз», а не «Этап … — релиз»).
4. **Защита ветки одной командой** — `scripts/ci/protect-branch.ps1`:
   payload с 6 required checks (`Lint (backend)`, `Test (backend)`,
   `Frontend`, `Security`, `E2E (Playwright)`, `Docker build`), review 1,
   запрет force-push/удаления; `-DryRun`/`-Verify`, exit 3 на 403 Free/private.
5. **Path-фильтры:** GitHub — `paths-ignore: ['docs/**', '**.md']` в
   `ci-selfhosted.yml`; GitFlic — `rules: changes: paths:` у `e2e` и `docker`
   (были раньше, здесь проверены и описаны).
6. **GitFlic-джоб `release`** (stage `release`, только `$CI_COMMIT_TAG`):
   проверяет наличие раздела релиза и складывает `notes.md` в артефакты;
   создание релиза (`release:`-ключ) закомментировано до live-проверки, чтобы
   неизвестная схема не сломала разбор конфига основных пайплайнов.
7. **Hosted `ci.yml` → ручной режим:** hosted-минуты заблокированы биллингом
   (KI-014), красный workflow не должен висеть на каждом PR; возврат — одна
   правка `on:`.
8. **Офлайн-путь зависимостей CI (KI-017):** wheelhouse в named volume
   `ai-teacher-wheelhouse` (`scripts/ci/build-wheelhouse.ps1`,
   Linux-колёса из зеркала) + `scripts/ci/install-python-deps.sh`
   (wheelhouse → pypi.org → зеркала aliyun/tsinghua) + кэши pip/pnpm
   (named volumes). PyPI с машины стал недоступен (TLS-таймауты), job `lint`
   до этого залипал в `pip install` на 20+ минут.
9. **Runner восстановлен:** прежний `C:\actions-runner` был во временном
   каталоге и исчез; runner перерегистрирован (`--replace`, labels
   `self-hosted, windows, ai-teacher`) и запущен в сессии пользователя.
10. **Документация:** `docs/CI.md` §9 (ADR), §10 (гейты), §11 (релиз),
    §12 (эксплуатация), §13 (ссылки); RULES §2.3/§5.1/§10/§11.19/§11.20;
    README-бейдж; CHANGELOG `[Unreleased]`; KNOWN_ISSUES (KI-014 → Resolved,
    KI-023); RELEASES (спринт 21); TODO_V0.3 (статусы).

---

## 2. Проверки

| Проверка | Команда/источник | Результат |
|----------|------------------|-----------|
| Ruff (backend, скоуп app/tests/scripts) | `ruff check app tests scripts` (venv) | **0** |
| Ruff в контейнере (как в CI) | `docker run … backend-lint.sh` c wheelhouse | **0** (после фикса `import sys`) |
| Frontend (как в CI) | `docker run … frontend.sh` с pnpm-кэшем | **PASS**: 80/80, build 78.71 kB gzip |
| Backend test job (как в CI) | `backend-test.sh` + pgvector/redis в docker-сети | **PASS**: 354 passed + 1 skip |
| YAML-конфиги | `yaml.safe_load` для 5 файлов CI | **OK** (jobs/stages на месте) |
| `protect-branch.ps1 -DryRun` | локально | payload с 6 checks |
| `protect-branch.ps1 -Verify` | локально | 403 «Upgrade to GitHub Pro…» → exit 1 |
| `check_version.py` | локально | OK: 0.2.0 во всех трёх файлах |
| `release_notes.py --list` / `0.2.0` | локально | `0.2.0`, заметки из журнала |
| `release_notes.py --version 9.9.9` | локально | exit 1 + список доступных релизов |
| CI (self-hosted), 6 job'ов | run (см. SPRINT-21) | **6/6 success** |

---

## 3. Файлы

```
+ .github/workflows/release.yml              — гейты → тег → Release
+ .github/workflows/ci-selfhosted.yml        — workflow_call, paths-ignore,
                                               named volumes wheelhouse/pip/pnpm
~ .github/workflows/ci.yml                   — ручной режим (KI-014) + paths-ignore
+ scripts/ci/protect-branch.ps1              — required checks + force-push
+ scripts/ci/build-wheelhouse.ps1            — офлайн-wheelhouse (Linux-колёса)
+ scripts/ci/install-python-deps.sh          — wheelhouse → PyPI → зеркала
~ scripts/ci/backend-lint.sh                 — install-python-deps, pip таймауты
~ scripts/ci/backend-test.sh                 — install-python-deps, pip таймауты
+ backend/scripts/release_notes.py           — заметки из docs/RELEASES.md
+ backend/scripts/check_version.py           — версия в трёх источниках
+ backend/tests/test_release_tools.py        — 13 тестов
~ gitflic-ci.yaml                            — job release (тег-пайплайн)
~ docs/CI.md                                 — §9–§13
~ docs/RULES.md                              — §2.3, §5.1, §10, §11.19, §11.20
~ docs/RELEASES.md, docs/CHANGELOG.md        — спринт 21 / [Unreleased]
~ docs/KNOWN_ISSUES.md                       — KI-014 → Resolved, KI-023
~ TODO_V0.3.md                               — статусы S21-001…006
~ README.md                                  — бейдж CI
```

---

## 4. Проблемы и отклонения

1. **PyPI недоступен с машины (KI-017), хуже чем раньше.** `pip install` в
   job'е `lint` висел 20+ минут: TLS-хендшейк к `pypi.org` таймаутил, при этом
   из свежего контейнера индекс открывался. Решение — офлайн-wheelhouse из
   зеркала + fallback на зеркала в `install-python-deps.sh`. Зеркала
   (`mirrors.aliyun.com`, `pypi.tuna.tsinghua.edu.cn`) отвечают стабильно.
2. **Required checks на GitHub недоступны** — 403 на Free/private. Скрипт
   готов, но применить его нельзя без Pro/публичного репозитория → KI-023.
3. **`workflow_dispatch` требует файла в default-ветке.** Поэтому живой
   dry-run релиза возможен только после мержа спринта в `main`; для проверки
   до мержа предусмотрен тег `v*-dryrun` (push тега читает workflow из тега).
4. **Java на машине 1.8, а PowerShell-агенту GitFlic нужен 11** — установка
   остаётся за владельцем вместе с registration token (KI-023,
   `docs/GITFLIC_RUNNER.md` §3).
5. **Первый (устаревший) PR-прогон** `41120196683` пришлось отменить вручную:
   `pip install` в контейнере залип, контейнер удалён, job завершился fail.
   Урок записан в RULES §11.20 (диагностика залипшего job).

---

## 5. Обоснование решений

- **`workflow_call` вместо дублирования гейтов.** Релиз обязан проверять то же,
  что PR; копия команд в двух файлах неизбежно разъедется. Побочный эффект:
  релиз видит ровно те же 6 job'ов и их таймауты.
- **Dry-run по умолчанию + тег `v*-dryrun`.** Релиз — необратимое действие
  (тег + публикация). Репетиция должна быть «дешёвой» и не требовать ручных
  флагов; тег `-dryrun` даёт живой прогон на runner'е, не создавая релиз, и не
  запускает второй прогон гейтов.
- **Заметки — из `RELEASES.md`, а не из коммитов.** Журнал уже пишется по
  правилам (RULES §2.4, §6); автоматический changelog из коммитов дал бы шум на
  русском и дублировал бы CHANGELOG.
- **Wheelhouse, а не «починить сеть».** Сеть — внешняя (KI-017); CI должен
  уметь работать без PyPI, а не зависеть от удачи. Тот же механизм станет
  основой S22-005 (`scripts/wheelhouse.py`).
- **Named volumes, а не `actions/cache`.** На self-hosted runner'е
  `actions/cache` требует дополнительных запросов к сервису и не работает для
  GitFlic; docker-volume — локальный, предсказуемый и переиспользуется между
  job'ами.
- **GitFlic `release:` не включаем «слепо».** Неизвестный ключ может сломать
  разбор конфига всех пайплайнов; job проверки заметок безопасен и полезен
  уже сейчас, а создание релиза включим после live-проверки схемы.

---

## 6. Что дальше

1. Дождаться зелёного PR-CI (6/6) на ветке спринта → мерж `sprint/21-ci` в
   `main` (PR #27).
2. После мержа: `gh workflow run release.yml -f version=0.2.0` (dry-run) —
   живая проверка релиз-пайплайна; затем тег `v0.2.0-dryrun` как репетиция
   «из тега».
3. Владельцу: GitFlic access token + Java 11 и agent registration → пилот
   (S21-002) → MR-гейт (S21-004) → закрытие KI-023.
4. Спринт 22: контрактные тесты (S22-001) → `fastapi`/`starlette` (KI-015),
   `pytest` 9 (KI-016), wheelhouse-скрипт (KI-017).
