/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Базовый URL REST API (по умолчанию /api/v1 через прокси) */
  readonly VITE_API_BASE?: string;
  /** Базовый URL WebSocket (например, ws://127.0.0.1:8000); пусто — same-origin */
  readonly VITE_WS_BASE?: string;
  /** Режим e2e: редактор кода заменяется на textarea (см. CodeEditor) */
  readonly VITE_E2E?: string;
  /** Sentry DSN на этапе сборки; в runtime переопределяется /config.js */
  readonly VITE_SENTRY_DSN?: string;
  /** Доля транзакций Sentry (0..1) */
  readonly VITE_SENTRY_TRACES_SAMPLE_RATE?: string;
  /** Релиз Sentry (версия + git-sha) */
  readonly VITE_APP_RELEASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
