import { defineConfig, devices } from '@playwright/test';

const BACKEND_PORT = Number(process.env.E2E_BACKEND_PORT ?? 8001);
const FRONTEND_PORT = Number(process.env.E2E_FRONTEND_PORT ?? 3100);
const E2E_DB = process.env.E2E_DB_NAME ?? 'ai_teacher_e2e';

// Backend запускается интерпретатором из venv: у системного python нет зависимостей.
// В CI переменная E2E_PYTHON=python (зависимости установлены глобально).
const PYTHON =
  process.env.E2E_PYTHON ??
  (process.platform === 'win32' ? 'venv\\Scripts\\python.exe' : 'venv/bin/python');

/**
 * E2E-конфиг (S11-001).
 *
 * Поднимает отдельный backend на тестовой БД с провайдером `echo` и dev-сервер
 * Vite, проксирующий /api на этот backend. Порт 8000 не занимается, поэтому
 * e2e не конфликтуют с локальной разработкой.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://127.0.0.1:${FRONTEND_PORT}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `${PYTHON} scripts/prepare_e2e_db.py && ${PYTHON} -m alembic upgrade head && ${PYTHON} scripts/seed_tasks.py && ${PYTHON} -m uvicorn app.main:app --host 127.0.0.1 --port ${BACKEND_PORT}`,
      cwd: '../backend',
      url: `http://127.0.0.1:${BACKEND_PORT}/api/v1/health`,
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
      env: {
        POSTGRES_DB: E2E_DB,
        LLM_PROVIDER: 'echo',
        RATE_LIMIT_ENABLED: 'false',
        DEBUG: 'false',
      },
    },
    {
      // Порт передаём флагом: env не всегда доходит до дочернего процесса
      command: `pnpm dev --host 127.0.0.1 --port ${FRONTEND_PORT} --strictPort`,
      url: `http://127.0.0.1:${FRONTEND_PORT}`,
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
      env: {
        VITE_PROXY_TARGET: `http://127.0.0.1:${BACKEND_PORT}`,
        // Редактор кода в e2e — textarea, чтобы не зависеть от CDN Monaco
        VITE_E2E: '1',
        // esbuild из pnpm-стора на Windows-runner'е не может писать файлы;
        // e2e-скрипт кладёт рабочую копию и передаёт путь сюда (см. e2e.ps1).
        ...(process.env.ESBUILD_BINARY_PATH
          ? { ESBUILD_BINARY_PATH: process.env.ESBUILD_BINARY_PATH }
          : {}),
      },
    },
  ],
});
