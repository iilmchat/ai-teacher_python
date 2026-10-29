# Sprint 8: Frontend Base — Отчёт

**Период:** 2026-10-29
**Статус:** ✅ Завершён

---

## 1. Файлы (+/-)

### Созданные (frontend)
```
+ frontend/package.json
+ frontend/pnpm-workspace.yaml          — onlyBuiltDependencies: esbuild (pnpm 12)
+ frontend/vite.config.ts               — React, Tailwind, alias, proxy, vitest
+ frontend/tsconfig.json / tsconfig.app.json / tsconfig.node.json
+ frontend/eslint.config.js             — flat config, TS + react-hooks
+ frontend/.prettierrc
+ frontend/.env.example                 — VITE_API_BASE
+ frontend/index.html
+ frontend/Dockerfile                   — node:22 → nginx:1.27
+ frontend/nginx.conf                   — SPA fallback, proxy /api, WebSocket
+ frontend/src/main.tsx, App.tsx, index.css, vite-env.d.ts
+ frontend/src/lib/api.ts               — fetch-обёртка, ApiError, авто-refresh
+ frontend/src/lib/token.ts             — токены в localStorage
+ frontend/src/store/auth.ts            — Zustand: вход, регистрация, уровень
+ frontend/src/types/api.ts             — типы контрактов backend
+ frontend/src/components/ui/{Button,Input,Card,Alert,Spinner}.tsx
+ frontend/src/components/layout/AppLayout.tsx
+ frontend/src/components/ProtectedRoute.tsx
+ frontend/src/pages/{HomePage,LoginPage,RegisterPage,ProfilePage,ComingSoonPage,NotFoundPage}.tsx
+ frontend/src/i18n/{index.ts,locales/ru.json,locales/en.json}
+ frontend/src/test/{setup.ts,utils.tsx,api.test.ts,auth-store.test.ts,LoginPage.test.tsx}
```

---

## 2. Покрытие

| Набор | Тестов | Что проверяет |
|-------|--------|----------------|
| `api.test.ts` | 6 | успех, `detail`, ошибки Pydantic, Bearer, refresh+retry, разлогин |
| `auth-store.test.ts` | 9 | вход, ошибка входа, регистрация, выход, смена уровня, `loadMe` |
| `LoginPage.test.tsx` | 5 | поля, отправка, ошибка, блокировка, ссылка на регистрацию |
| **Итого** | **20** | |

---

## 3. Результаты

| Проверка | Команда | Результат |
|----------|---------|-----------|
| Типы | `pnpm typecheck` | 0 ошибок |
| Линтер | `pnpm lint` | 0 ошибок |
| Тесты | `pnpm test` | `20 passed` |
| Сборка | `pnpm build` | `dist/index-*.js 333.19 kB │ gzip 105.49 kB` |
| Preview | `vite preview` | `/` → 200, `/login` → 200 (SPA fallback) |

---

## 4. Smoke

```
GET http://127.0.0.1:4173/        → 200, <div id="root"> присутствует
GET http://127.0.0.1:4173/login   → 200 (SPA fallback от Vite)
```

Сценарий в браузере против backend не автоматизирован (KI-012).

---

## 5. Что не так

1. **KI-012:** нет e2e/Playwright и проверки с живым backend; образ фронтенда
   не собирался в этой сессии.
2. Стора `chat`/`tasks` и страницы чата/задач — заглушки до спринта 9.
3. `Modal` не создан (не нужен до спринта 9).
4. Тестов hooks пока нет: `useChat`/`useWebSocket` появятся вместе со страницами.

---

## 6. Новые KI

| ID | Статус | Severity | Суть |
|----|--------|----------|------|
| KI-012 | Open | Low | Нет e2e-тестов и проверки с живым backend |

---

## 7. Обоснование

- **TypeScript strict + project references.** `tsc -b` проверяет и приложение,
  и конфиг Vite раздельно — ошибки не смешиваются.
- **Токены вне Zustand.** `lib/token.ts` разрывает циклический импорт
  `store → api → store`; стор хранит только профиль и статус.
- **Авто-refresh в API-клиенте.** Один повтор запроса после 401; при неудаче —
  очистка токенов и событие `auth:unauthorized`, стор разлогинивает.
- **Ошибки Pydantic склеиваются.** Пользователь видит «Поле обязательно;
  Слишком короткий пароль» вместо `[object Object]`.
- **i18n с первого дня.** RULES §3.2 запрещает хардкод строк в JSX; ключи
  добавлены вместе с компонентами.
- **Vite-прокси вместо CORS.** В dev фронтенд обращается к `/api/v1`, запросы
  уходят на `127.0.0.1:8000`; на проде это делает nginx.
- **nginx для SPA.** `try_files ... /index.html` обязателен: иначе прямой заход
  на `/tasks` даёт 404 от nginx.

---

**Дата:** 2026-10-29
