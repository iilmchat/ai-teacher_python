import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { createElement } from 'react';
import { afterEach, beforeEach, expect, vi } from 'vitest';
import * as axeMatchers from 'vitest-axe/matchers';

expect.extend(axeMatchers);

// Monaco загружается lazy-чанком: подменяем его до импорта страницы
vi.mock('@/components/code-editor/MonacoEditor', () => ({
  default: ({
    value,
    onChange,
  }: {
    value: string;
    onChange?: (value: string) => void;
  }) =>
    createElement('textarea', {
      'data-testid': 'monaco-mock',
      value,
      onChange: (event: { target: HTMLTextAreaElement }) =>
        onChange?.(event.target.value),
    }),
}));

// Каждый тест начинается с чистого localStorage и моков
beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

afterEach(() => {
  cleanup();
});
