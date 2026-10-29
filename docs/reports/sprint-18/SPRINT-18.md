# Sprint 18: UX, A11y & Design System — Отчёт

**Период:** 2026-10-30
**Статус:** ✅ Завершён (карточный вид таблиц и аудит хардкода — с оговорками)

---

## 1. Файлы (+/-)

### Frontend
```
+ components/ui/Modal.tsx               — доступная модалка (Escape, focus)
+ components/ui/Toast.tsx               — тост и стек с aria-live
+ components/ui/Tabs.tsx                — табы с role=tab/tabpanel
+ components/ui/Table.tsx               — таблица + Th/Td
+ components/ui/Badge.tsx               — бейджи
+ components/ui/Skeleton.tsx            — заглушки загрузки
+ components/ui/ThemeToggle.tsx         — переключатель темы
+ pages/DevUiPage.tsx                   — storybook-lite (dev only)
+ store/theme.ts                        — тема, localStorage, класс dark
+ test/a11y.test.tsx                    — 2 axe-теста
+ test/theme.test.ts                    — 2 теста темы
~ index.css                             — токены, dark-слой
~ components/layout/AppLayout.tsx       — skip-link, мобильное меню, тема
~ pages/ChatPage.tsx                    — drawer сессий
~ pages/ProfilePage.tsx                 — карточка оформления
~ components/code-editor/MonacoEditor.tsx — vs/vs-dark
~ components/AdminRoute.tsx / TeacherRoute.tsx — i18n
~ App.tsx                               — /dev/ui только dev
~ test/setup.ts, test/vitest.d.ts       — vitest-axe matcher
~ package.json / pnpm-lock.yaml         — axe-core, vitest-axe
~ i18n locales                          — theme, a11y, access, chat drawer
```

### Документы
```
~ USER_GUIDE, MANUAL_TESTING_GUIDE, ARCHITECTURE, RULES §11.17
~ README, docs/README, TODO_V0.2, RELEASES, CHANGELOG
+ docs/reports/sprint-18/SPRINT-18.md
```

---

## 2. Покрытие

| Уровень | Было | Стало |
|---------|------|-------|
| Frontend unit | 76 | **80** (+4) |
| Axe-тесты | — | 2 страницы, 0 нарушений |
| Backend | 271 | 271 (без изменений) |

Новые тесты: axe на входе и регистрации; применение/переключение темы
и сохранение в `localStorage`.

---

## 3. Результаты

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Frontend | `pnpm typecheck && lint && test` | 80 passed, 0/0 |
| Сборка | `pnpm build` | 0 ошибок, entry **78.71 kB** gzip |
| Офлайн | `pnpm test:offline` | CDN-ссылок нет |
| Dev-страница | проверка `dist/assets` | чанка `DevUiPage` нет |
| Backend | `pytest -q` | 271 passed (без изменений) |

---

## 4. Smoke

1. Переключить тему в шапке → весь интерфейс тёмный, после перезагрузки
   сохраняется; Monaco на `/code` — `vs-dark`.
2. Tab с начала страницы → skip-link; Enter переводит к `main`.
3. 375 px: гамбургер открывает меню; в чате ☰ открывает drawer сессий,
   overlay/✕ закрывают.
4. `/dev/ui` в dev показывает Badge/Skeleton/Table/Modal/Toast/Tabs;
   после `pnpm build` маршрута и чанка нет.
5. Axe: вход и регистрация — 0 нарушений (кроме отключённого contrast).

---

## 5. Что не так

- **Карточный вид таблиц на мобильных не сделан:** используется
  горизонтальный скролл внутри контейнера.
- **Аудит хардкода не автоматизирован;** 8 fallback-ошибок в `api.ts`,
  `auth.ts`, `chatSocket.ts` остаются на русском (не JSX-строки).
- **Контраст не проверяется автоматически:** jsdom не считает цвета,
  `color-contrast` отключён в axe; ручной чек-лист в
  `MANUAL_TESTING_GUIDE`.
- Тёмная тема для старых экранов — слой CSS-переопределений, а не `dark:`
  в каждом компоненте; при добавлении новых цветов нужно дополнять слой.
- `/dev/ui` использует английские подписи (dev-only, вне i18n).
- CI не стартовал (KI-014, биллинг) — мерж по временному разрешению.

---

## 6. Новые KI

Нет. Открыт только KI-014 (CI/биллинг).

---

## 7. Обоснование

- **CSS-переменные + класс `dark`.** Позволяет перекрасить все существующие
  экраны без правки десятков компонентов; новые компоненты сразу на токенах.
- **Тема в Zustand + localStorage.** Единый источник для шапки, профиля и
  Monaco; `applyTheme` до рендера убирает вспышку светлой темы.
- **`/dev/ui` через `import.meta.env.DEV ? lazy(...) : null`.** Проверено
  сборкой: чанк исчезает из прод-бандла.
- **Axe в jsdom с отключённым contrast.** Остальные правила ловят реальные
  ошибки разметки; контраст проверяется вручную, т.к. jsdom не layout.
- **Drawer сессий, а не вторая колонка.** На 375 px колонка 260 px оставляла
  бы чату ~100 px; drawer освобождает всю ширину.
