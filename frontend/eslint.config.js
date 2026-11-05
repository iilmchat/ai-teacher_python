import js from '@eslint/js';
import globals from 'globals';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  {
    // coverage и отчёты Playwright — сгенерированные файлы
    ignores: ['dist', 'node_modules', 'coverage', 'test-results', 'playwright-report'],
  },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Правила React Compiler из eslint-plugin-react-hooks 7: они требуют
      // переписать загрузку данных во всех страницах (10 файлов) и рассчитаны
      // на экспериментальный компилятор. Пока приложение грузит данные через
      // `load()` в эффекте — отключаем, миграция отдельной задачей.
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/refs': 'off',
      'react-hooks/preserve-manual-memoization': 'off',
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      // Строки интерфейса — только через i18n (RULES §3.2)
      'no-console': ['warn', { allow: ['warn', 'error'] }],
    },
  },
);
