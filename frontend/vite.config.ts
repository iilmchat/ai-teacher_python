// defineConfig из vitest/config добавляет типизацию секции `test`
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: Number(process.env.VITE_DEV_PORT ?? 3000),
    // Запросы к API проксируются на backend, чтобы не настраивать CORS в dev.
    // E2E поднимает backend на отдельном порту через VITE_PROXY_TARGET.
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    // Основной чанк держим в пределах 200 kB gzip (RULES §3.2)
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        // S19-002: vendor отдельно, entry остаётся маленьким.
        // S42-001: сторы вынесены отдельным чанком — иначе рост состояния
        // (черновики, история попыток) двигает entry к лимиту 80 kB gzip,
        // зафиксированному в docs/ARCHITECTURE.md.
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          i18n: ['i18next', 'react-i18next'],
          stores: [
            './src/store/auth.ts',
            './src/store/chat.ts',
            './src/store/tasks.ts',
            './src/store/theme.ts',
          ],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    // e2e-спеки Playwright не должны попадать в Vitest
    exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text-summary', 'html'],
      include: ['src/lib/**', 'src/store/**'],
      thresholds: {
        lines: 70,
        functions: 70,
        branches: 60,
        statements: 70,
      },
    },
  },
});
