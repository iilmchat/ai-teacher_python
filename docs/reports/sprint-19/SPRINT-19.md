# Sprint 19: Performance & Scale — Отчёт (частично)

**Период:** 2026-10-29
**Статус:** ⚠️ S19-001/002 выполнены; S19-003…006 отложены после S16

---

## 1. Файлы (+/-)

```
+ frontend/src/lib/monacoSetup.ts            — локальные пути + worker
+ frontend/src/components/code-editor/MonacoEditor.tsx — AMD-редактор, lazy
+ frontend/scripts/copy-monaco.mjs           — копирование min/vs в public
+ frontend/scripts/check-offline.mjs         — проверка отсутствия CDN
~ frontend/src/components/code-editor/CodeEditor.tsx — lazy + e2e textarea
~ frontend/src/App.tsx                      — React.lazy всех страниц
~ frontend/vite.config.ts                   — manualChunks react/i18n
~ frontend/package.json                     — monaco-editor, test:offline
~ frontend/pnpm-lock.yaml
~ .gitignore                                — public/monaco исключён
+ docs/reports/sprint-19/SPRINT-19.md
```

---

## 2. Покрытие

| Проверка | Было | Стало |
|----------|------|-------|
| Frontend unit | 71 | 71 (регресс не добавлен) |
| Offline-check | — | `pnpm test:offline` |

---

## 3. Результаты

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Сборка | `pnpm build` | 0 ошибок |
| Офлайн | `pnpm test:offline` | CDN-ссылок нет |
| Бандл | Vite | entry **76.29 kB gzip**, react 15.3, i18n 18.4, Monaco 1 kB + assets |
| Frontend тесты | `pnpm test` | 71 passed |

---

## 4. Smoke

1. `pnpm build` → `dist/monaco/vs` содержит локальные ассеты Monaco.
2. `pnpm test:offline` → «no CDN references in dist/assets».
3. Открыть `/code` в обычном режиме: редактор загружается с `/monaco/vs`,
   worker — `/monaco/vs/base/worker/workerMain.js`.
4. E2E (`VITE_E2E=1`) по-прежнему использует textarea, Monaco не грузится.
5. Навигация по страницам: каждая страница — отдельный чанк, entry ≤80 kB.

---

## 5. Что не так

- **Отложены S19-003…006:** Redis-кэш, оптимизация запросов, pgvector-поиск и
  нагрузочный тест требуют классов/нагрузки из S16; делать их сейчас — без
  данных для оптимизации.
- Prefetch по hover не реализован: чанки малы, выигрыш незначителен.
- Локальные ассеты Monaco (~10 МБ) копируются в `dist` — приемлемо для
  офлайн-развёртывания, но увеличивает образ frontend.
- Windows-сборка ESM-варианта Monaco падала на удалении temp-файла esbuild
  (AV/локировка), поэтому выбран AMD-вариант с копированием ассетов.

---

## 6. Новые KI

Нет. **KI-013 закрыт:** Monaco больше не зависит от CDN.

---

## 7. Обоснование

- **AMD-ассеты вместо ESM-бандла.** ESM-вариант добавлял 8 МБ temp-файл
  esbuild и падал на Windows; AMD `min/vs` копируется как статика, грузится
  только при открытии редактора, CDN не используется.
- **Lazy `MonacoEditor`.** Редактор не нужен на главной/в чате; отдельный чанк
  уменьшает первый бандл.
- **manualChunks.** React и i18n вынесены в vendor-чанки, entry — 76 kB gzip.
- **`test:offline` в сборке.** Проверка строк в бандле ловит случайное
  возвращение CDN-ссылок без запуска браузера.
