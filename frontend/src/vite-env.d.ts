/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Базовый URL REST API (по умолчанию /api/v1 через прокси) */
  readonly VITE_API_BASE?: string;
  /** Базовый URL WebSocket (например, ws://127.0.0.1:8000); пусто — same-origin */
  readonly VITE_WS_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
