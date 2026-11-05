# SPRINT-30.md — Release v0.3.0 (Ops & Scale)

**Период:** 2026-11-01  
**Задачи:** S30-001…S30-004  
**Статус:** ✅ релиз собран: UPGRADE, версия 0.3.0 во всех источниках, полные
гейты, тег `v0.3.0` и GitHub Release через `release.yml`

---

## 1. Файлы (+/-)

```
+ docs/UPGRADE.md                               — обновление v0.2.0 → v0.3.0
+ docs/reports/sprint-30/SPRINT-30.md           — этот отчёт
+ frontend/src/pages/GradebookPage.tsx          — журнал оценок (UI)
+ frontend/src/lib/download.ts                  — сохранение CSV
+ frontend/src/test/gradebook.test.tsx          — 3 теста
~ pyproject.toml / backend/app/config.py / frontend/package.json — 0.3.0
~ README.md                                    — версия, спринты 1–30, UPGRADE
~ docs/CHANGELOG.md                            — [0.3.0]
~ docs/RELEASES.md                             — «Релиз v0.3.0» + спринт 30
~ docs/KNOWN_ISSUES.md                         — KI-024, KI-025
~ docs/MANUAL_TESTING_GUIDE.md                 — §18 приёмочный чек-лист
~ TODO_V0.3.md                                 — S30-001…004 [x]
~ frontend/src/pages/ClassroomDetailPage.tsx   — «Скачать отчёт», массовое
  назначение, ссылка на журнал
~ frontend/src/App.tsx / src/types/api.ts / src/lib/api.ts — маршрут, типы, download
~ frontend/src/i18n/locales/{ru,en}.json       — ключи gradebook/report/bulk
```

---

## 2. Гейты (S30-002)

| Проверка | Результат |
|----------|-----------|
| `ruff check app tests scripts` | 0 |
| `mypy app` (strict) | 0 |
| `pytest -q` | **501 passed + 1 skipped** |
| `alembic upgrade head && alembic check` | OK (013) |
| `check_version.py` | 0.3.0 везде |
| `release_notes.py --version 0.3.0` | раздел найден |
| frontend `typecheck` / `lint` | 0 / 0 |
| frontend `test` | **90 passed** (16 файлов) |
| frontend `build` / `test:offline` | OK / OK |
| `check-i18n.mjs` | 325 ключей, кириллицы вне локалей нет |
| e2e (локально) | 17 passed / 1 skipped |
| CI (PR) | **7/7 success** |

---

## 3. Артефакты релиза

- Версия `0.3.0` в `pyproject.toml`, `frontend/package.json`,
  `backend/app/config.py` (отдаётся в `/api/v1/health`).
- Тег `v0.3.0` и GitHub Release создаются workflow `release.yml`
  (`gh workflow run release.yml -f version=0.3.0 -f dry_run=false`); заметки —
  раздел «## Релиз v0.3.0» из `docs/RELEASES.md`.
- `docs/UPGRADE.md` — порядок обновления, новые ENV, откат.

---

## 4. Сделано сверх S30 (остатки UI из 26/28)

- Кнопка «Скачать отчёт» на странице класса (`GET /classrooms/{id}/report`).
- Массовое назначение: мультивыбор задач + `POST .../assignments/bulk`
  с отчётом `created/skipped`.
- Страница журнала оценок `/classrooms/:id/gradebook` + «Скачать CSV»
  (`/gradebook/csv`), ссылка со страницы класса.
- Тесты: `gradebook.test.tsx` (матрица, CSV, ошибка), 90 frontend-тестов.

---

## 5. Что не так

1. **UI-остатков больше нет**, но шаблоны назначений (S28-002) остаются
   API-only: отдельного экрана для шаблонов нет (создание/применение — через
   API); это не блокер релиза, зафиксировано здесь.
2. **Метрики LLM/кэша — на процесс** (KI-024), retention — вручную/по cron
   (KI-025).
3. **GitHub Release** создаётся workflow'ом после мержа; если runner занят,
   тег появляется с задержкой (ретрай — повторный запуск workflow).

---

## 6. Новые KI

- **KI-024** (Accepted, Low): метрики LLM/кэша считаются на процесс.
- **KI-025** (Accepted, Low): retention запускается вручную/по cron.

---

## 7. Обоснование

1. **UPGRADE.md как контракт обновления.** Миграции 011–013 аддитивные, но
   эксплуатации нужен явный порядок (бэкап → env → миграции → пересборка) и
   точка отката (`downgrade 010`).
2. **Версия в трёх источниках.** `check_version.py` в релиз-workflow не даёт
   выпустить тег с рассогласованной версией (иначе `/health` врёт).
3. **Заметки из журнала, а не из коммитов.** `release_notes.py` берёт раздел
   «## Релиз v0.3.0» — релиз описывается один раз и попадает в GitHub Release.
4. **UI-остатки закрыты до релиза.** API без UI — это «недоделка» с точки зрения
   пользователя; три экрана/кнопки добавлены до тега, чтобы v0.3.0 не уходил
   с `[~]` в TODO.
