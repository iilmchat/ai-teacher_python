import { act } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { useThemeStore } from '@/store/theme';

afterEach(() => {
  act(() => useThemeStore.getState().setTheme('light'));
});

describe('theme store', () => {
  it('переключает тёмную тему и класс на html', () => {
    act(() => useThemeStore.getState().setTheme('dark'));

    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(localStorage.getItem('ai-teacher.theme')).toBe('dark');
  });

  it('toggle возвращает светлую тему', () => {
    act(() => useThemeStore.getState().setTheme('dark'));
    act(() => useThemeStore.getState().toggle());

    expect(useThemeStore.getState().theme).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });
});
