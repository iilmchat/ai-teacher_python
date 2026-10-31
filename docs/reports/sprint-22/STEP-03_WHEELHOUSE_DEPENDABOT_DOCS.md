# Шаг 03/спринт 22: wheelhouse, Dependabot, документация

**Дата:** 2026-10-31  
**Спринт:** 22 (v0.3.0)  
**Задачи:** S22-004, S22-005, S22-006  
**Статус:** ✅ выполнено (авто-мерж Dependabot — KI-023)

---

## 1. Что сделано

1. **`scripts/wheelhouse.py`** (S22-005, KI-017) — офлайн-установка:
   - `build --out .wheelhouse [--docker] [--index-url ...]` — скачать все пины
     `backend/requirements.txt`; `--docker` запускает `python:3.12-slim`, чтобы
     колёса были под Linux (в CI их и используют);
   - `install --from .wheelhouse --python <interp>` — `pip install --no-index
     --find-links` (без сети);
   - `list --from .wheelhouse` — что лежит.
   Скрипт — единственная реализация скачивания: `scripts/ci/build-wheelhouse.ps1`
   теперь только монтирует named volume и вызывает его в контейнере.
2. **Wheelhouse пересобран** под новые пины: 101 колесо, 75 МБ (Linux
   `manylinux`), лint/test/security job'ы ставят зависимости офлайн (проверено
   локально: `backend-lint.sh` → «wheelhouse OK», ruff/mypy 0).
3. **Dependabot (S22-004):**
   - политика зафиксирована в `.github/dependabot.yml` и `docs/CI.md` §13:
     minor/patch — группой, мерж после зелёного CI; major — отдельным PR и
     ручной проверкой; лимит 5 PR на экосистему;
   - **авто-мерж недоступен** на GitHub Free/private (нет branch protection и
     auto-merge) — записано в KI-023;
   - закрыты устаревшие PR после ручного апгрейда (#18, #20, #22), чтобы
     Dependabot пересобрал группы от актуальных пинов.
4. **Документация (S22-006):**
   - RULES §11.21 «Обновление зависимостей» (контрактные тесты → установка →
     pytest/e2e → пины → `pip-audit` без игноров → CHANGELOG/SPEC; отдельно —
     поведенческие изменения и `filterwarnings`);
   - GETTING_STARTED §4 «Если PyPI недоступен: wheelhouse»;
   - ARCHITECTURE — фактические версии и путь аудита;
   - CI.md §13 — Dependabot и политика мержа;
   - KNOWN_ISSUES: KI-015/016/017 → `Resolved`; CHANGELOG `[Unreleased]`; TODO.

---

## 2. Проверки

| Проверка | Команда | Результат |
|----------|---------|-----------|
| wheelhouse list | `pwsh scripts/ci/build-wheelhouse.ps1 -ListOnly` | 101 колесо, Linux |
| офлайн-установка + lint | `docker run … backend-lint.sh` (wheelhouse `:ro`) | «wheelhouse OK», ruff/mypy 0 |
| security job без игноров | `docker run … security-backend.sh` | «No known vulnerabilities found» |
| YAML CI-конфигов | `yaml.safe_load` (4 файла) | OK |
| Dependabot PR | `gh pr list` | 3 устаревших закрыты с пояснением |

---

## 3. Файлы

```
+ scripts/wheelhouse.py                 — build/install/list (offline)
~ scripts/ci/build-wheelhouse.ps1       — обёртка над wheelhouse.py (volume)
~ .github/dependabot.yml                — политика S22-004
~ .gitignore                            — .wheelhouse/
~ docs/GETTING_STARTED.md               — §4 wheelhouse
~ docs/CI.md                            — §13 Dependabot
~ docs/RULES.md                         — §11.21
~ docs/ARCHITECTURE.md                  — версии/аудит
~ docs/KNOWN_ISSUES.md                  — KI-015/016/017 Resolved
```

---

## 4. Проблемы и отклонения

1. **`docker volume rm` не всегда удаляет том** (занят предыдущим контейнером):
   при `-Recreate` в wheelhouse остались колёса старых версий. На установку не
   влияет (pip берёт версию по пину), но объём растёт. Записано в §5.
2. **Авто-мерж Dependabot не реализуем** на текущем тарифе: нужен Pro
   (branch protection + auto-merge) или GitFlic. Политика мержа — вручную,
   отслеживается в KI-023.
3. **Публичные действия GitHub обновлять не стали:** PR #12–#14 (`checkout@7`,
   `setup-python@7`, `setup-node@7`) — мажорные, требуют проверки, что
   self-hosted job'ы не сломаются; оставлены на ручной разбор (major-политика).

---

## 5. Обоснование

- **Один инструмент вместо двух.** `build-wheelhouse.ps1` и `wheelhouse.py`
  делали одно и то же; теперь PS-обёртка нужна только ради named volume
  (docker-специфика CI), а логика — в Python-скрипте, который работает и на
  хосте, и в контейнере.
- **`--docker` по умолчанию в документации.** Колёса, собранные pip'ом
  Windows-хоста, в Linux-контейнеры не ставятся — самая частая ловушка
  офлайн-установки; `--docker` убирает её из процесса.
- **Dependabot без авто-мержа — осознанно.** Автомерж minor/patch без
  branch protection означал бы мерж «чего угодно» по красному CI; на Free это
  технически невозможно, а имитировать API-мержем — опасно. Ручной мерж после
  зелёного CI — правило RULES §10 до закрытия KI-023.
