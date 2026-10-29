/**
 * Локальная загрузка Monaco (S19-001, закрывает KI-013).
 *
 * Ассеты `monaco-editor/min/vs` копируются в `public/monaco/vs` скриптом
 * `scripts/copy-monaco.mjs` (prebuild/predev). AMD-loader подключается с
 * собственного origin, CDN не используется.
 */

const MONACO_BASE = '/monaco/vs';

interface MonacoEnvironmentShape {
  getWorkerUrl: () => string;
}

(self as unknown as { MonacoEnvironment: MonacoEnvironmentShape }).MonacoEnvironment = {
  getWorkerUrl: () => `${MONACO_BASE}/base/worker/workerMain.js`,
};

export const MONACO_LOADER_URL = `${MONACO_BASE}/loader.js`;
export const MONACO_EDITOR_MODULE = 'vs/editor/editor.main';
