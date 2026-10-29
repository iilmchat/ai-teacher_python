import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { createElement } from 'react';
import { afterEach, beforeEach, vi } from 'vitest';

// Monaco в jsdom не работает: подменяем редактор обычной textarea
vi.mock('@monaco-editor/react', () => ({
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
