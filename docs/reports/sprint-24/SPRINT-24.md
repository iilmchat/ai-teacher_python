# SPRINT-24.md — Sandbox Runner Isolation (v0.3.0)

**Период:** 2026-10-31  
**Задачи:** S24-001…S24-005  
**Статус:** ✅ контейнер-раннер реализован, изоляция проверена self-check'ом и
21 тестом; режим по умолчанию — `native` (контейнер включается флагом)

---

## 1. Файлы (+/-)

```
+ backend/sandbox_runner/Dockerfile       — образ: python:3.12-slim +
                                            RestrictedPython + ядро песочницы
+ backend/sandbox_runner/runner.py        — протокол stdin/stdout JSON + --self-check
+ backend/app/core/sandbox_runtime.py     — чистое ядро (вынесено из executor)
+ backend/app/core/container_sandbox.py   — docker run с флагами изоляции,
                                            метрики, fallback на native
~ backend/app/core/executor.py            — EXECUTOR_MODE, контейнерный путь,
                                            реэкспорт ядра
~ backend/app/config.py                   — executor_mode/executor_image
+ backend/tests/test_container_sandbox.py — 9 тестов (команда, протокол, fallback)
+ backend/tests/test_container_isolation.py — 21 тест (self-check, атаки, лимиты)
+ scripts/ci/build-sandbox-image.ps1      — сборка образа + self-check
~ scripts/ci/docker.ps1                   — сборка образа раннера и self-check в CI
~ .env.example                            — EXECUTOR_MODE/EXECUTOR_IMAGE
~ docs/ARCHITECTURE.md, SPEC.md, RULES.md, GETTING_STARTED.md,
  DESIGN_ADMIN_AND_OPS.md, CHANGELOG.md, KNOWN_ISSUES.md, RELEASES.md, TODO_V0.3.md
```

---

## 2. Покрытие

- **Команда изоляции (9 тестов):** все флаги (`--network none`, `--read-only`,
  `--cap-drop ALL`, `no-new-privileges`, `--user 65534:65534`, `--tmpfs`,
  `--memory/--memory-swap`, `--pids-limit`, `--pull never`), протокол,
  метрики, fallback при отсутствии Docker и при отсутствии образа,
  ненавязчивость native-режима.
- **Изоляция (21 тест, требуют Docker + образ):** self-check (`uid=65534`,
  read-only rootfs, tmpfs пишется, сеть недоступна, `CapEff=0`), батч в
  контейнере, изоляция кейсов, 14 атакующих векторов, лимит памяти, таймаут и
  восстановление, обрезка вывода.
- **Непокрытое:** поведение на Linux-хосте с rootless Docker — проверяется
  при развёртывании (self-check для этого и существует).

---

## 3. Результаты

| Проверка | Результат |
|----------|-----------|
| `ruff check app tests scripts` | 0 |
| `mypy app` (strict) | 0 |
| Контейнерные тесты | **30 passed** (9 unit + 21 isolation) |
| self-check образа | read-only ✓, tmpfs ✓, network=none ✓, caps=0 ✓, uid=65534 ✓ |
| Контейнерный батч | `print(input()*2)` → `aa`, `bb` |
| Fallback (нет образа/Docker) | нативный режим, результат `2` |
| Полный прогон | см. SPRINT-24 в RELEASES (430+ тестов) |

---

## 4. Smoke

```powershell
pwsh scripts/ci/build-sandbox-image.ps1 -SelfCheck
$env:EXECUTOR_MODE='container'
pytest -q tests/test_container_isolation.py
```

---

## 5. Что не так

1. **Режим по умолчанию — `native`.** План S24-001 требует `native` до
   проверки; контейнерный режим включается `EXECUTOR_MODE=container`. Для
   включения в production нужно: собрать образ на хосте и убедиться, что
   self-check проходит и добавленная latency приемлема (старт контейнера
   ~0.6–1 с против ~0.3 с у нативного пула).
2. **Нет пула контейнеров.** Каждый батч — новый контейнер (S24-004
   предполагал кэш/пул). Для класса этого достаточно, но при 5+ RPS контейнеры
   станут узким местом; кэш — кандидат в v0.3.x.
3. **Windows-специфика Docker CLI.** `shutil.which("docker")` возвращает шим
   без `.exe` → CreateProcess падает с WinError 193; исправлено поиском
   `docker.exe` (записано в RULES §11.8).
4. **В CI образ проверяется в `docker`-job** (сборка + self-check), а
   контейнерные тесты пропускаются в `test`-job (внутри контейнера нет Docker
   socket) — они прогоняются на машине разработки/runner'е.

---

## 6. Новые KI

Нет. Технический долг S13-006 (изоляция только процессами ОС) закрыт для
контейнерного режима; ограничение «по умолчанию native» — осознанное решение,
а не KI.

---

## 7. Обоснование

1. **Ядро песочницы вынесено в отдельный модуль.** Образ должен оставаться
   минимальным (stdlib + RestrictedPython): иначе контейнер тащит pydantic,
   sqlalchemy и БД-клиенты, которые ему не нужны и увеличивают поверхность атаки.
2. **Протокол тот же, что у батча.** Один и тот же формат stdin/stdout JSON
   позволяет сравнивать режимы, использовать общий разбор результатов и не
   плодить второй контракт.
3. **Self-check вместо «доверия флагам».** Флаги можно забыть/ослабить при
   изменении команды; проверка изнутри контейнера (uid, read-only, сеть, caps)
   ловит регресс в CI и при развёртывании.
4. **Fallback, а не отказ.** Если Docker недоступен (Windows dev, урезанный
   стенд), submit не должен падать: контейнерный режим откатывается на нативный
   с warning и счётчиком `fallbacks`.
5. **По умолчанию native.** Контейнер добавляет latency и требует собранного
   образа; включать его стоит осознанно, когда изоляция важнее задержки —
   это решение эксплуатации, а не дефолт.
