import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { api } from '@/lib/api';
import { TaskDetailPage } from '@/pages/TaskDetailPage';
import { useTasksStore } from '@/store/tasks';
import { renderWithRouter } from '@/test/utils';

// Monaco грузится лениво и в jsdom не рендерится — подменяем редактор
// простым textarea, чтобы проверять значение кода в редакторе.
vi.mock('@/components/code-editor/CodeEditor', () => ({
  CodeEditor: ({
    value,
    onChange,
  }: {
    value: string;
    onChange: (value: string) => void;
  }) => (
    <textarea
      data-testid="code-input"
      aria-label="Редактор кода"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  ),
}));
import type { SubmitResponse, TaskDetail } from '@/types/api';

const TASK_ID = '77777777-7777-7777-7777-777777777777';

const DETAIL: TaskDetail = {
  id: TASK_ID,
  title: 'Сумма двух чисел',
  description: 'Считайте два числа и выведите их сумму.',
  difficulty: 'easy',
  category: 'input_output',
  hints: [],
  solution_template: 'a = int(input())\nb = int(input())\nprint(a + b)\n',
  test_cases_count: 2,
  status: 'not_started',
  attempts: 0,
};

const CHECK: SubmitResponse = {
  passed: false,
  passed_count: 0,
  total_count: 2,
  attempts: 0,
  status: 'not_started',
  results: [
    {
      index: 1,
      passed: false,
      description: 'Положительные',
      input: '2\n3\n',
      expected_output: '5',
      actual_output: '0',
      error: null,
    },
  ],
  message: 'Пройдено 0 из 2 тестов. Пробная проверка — попытка не засчитывается.',
  practice: true,
};

function resetStore(): void {
  useTasksStore.setState({
    tasks: [],
    detail: null,
    progress: null,
    submission: null,
    checkResult: null,
    filters: {
      difficulty: null,
      category: null,
      tag: null,
      status: null,
      search: '',
    },
    loading: false,
    submitting: false,
    checking: false,
    error: null,
  });
}

describe('TaskDetailPage', () => {
  beforeEach(() => {
    resetStore();
    vi.restoreAllMocks();
  });

  it('показывает кнопку пробной проверки и подсказку', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
      if (path.endsWith('/attempts')) {
        return { items: [], total: 0 };
      }
      return DETAIL;
    });

    renderWithRouter(<TaskDetailPage />, { route: `/tasks/${TASK_ID}` });

    expect(await screen.findByRole('button', { name: /Пробная проверка/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Отправить решение/ })).toBeTruthy();
    expect(screen.getByText(/не засчитывается в попытки/)).toBeTruthy();
  });

  it('ведёт в чат с контекстом задачи', async () => {
    vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
      if (path.endsWith('/attempts')) {
        return { items: [], total: 0 };
      }
      return DETAIL;
    });

    renderWithRouter(<TaskDetailPage />, { route: `/tasks/${TASK_ID}` });

    const link = await screen.findByRole('link', {
      name: 'Спросить ассистента',
    });
    expect(link).toHaveAttribute('href', `/chat?task=${TASK_ID}`);
  });

  it('показывает историю попыток и возвращает код в редактор', async () => {
    const user = userEvent.setup();
    const attempt = {
      id: 'att-1',
      task_id: TASK_ID,
      passed: false,
      passed_count: 1,
      total_count: 2,
      created_at: '2026-11-05T10:00:00',
    };
    vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
      if (path.endsWith('/attempts')) {
        return { items: [attempt], total: 1 };
      }
      if (path.includes('/attempts/')) {
        return {
          ...attempt,
          code: 'print(42)',
          results: [],
        };
      }
      return DETAIL;
    });

    renderWithRouter(<TaskDetailPage />, { route: `/tasks/${TASK_ID}` });

    expect(await screen.findByText('История попыток')).toBeTruthy();
    expect(screen.getByText(/Не решено/)).toBeTruthy();

    await user.click(screen.getByRole('button', { name: 'Подробнее' }));

    expect(await screen.findByText('print(42)')).toBeTruthy();

    await user.click(
      screen.getByRole('button', { name: 'Вернуть код в редактор' }),
    );
    const editor = (await screen.findByTestId('code-input')) as HTMLTextAreaElement;
    expect(editor.value).toBe('print(42)');
  });

  it('пробная проверка показывает разбор, не меняя попытки', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
      if (path.endsWith('/attempts')) {
        return { items: [], total: 0 };
      }
      return DETAIL;
    });
    const post = vi.spyOn(api, 'post').mockResolvedValue(CHECK);

    renderWithRouter(<TaskDetailPage />, { route: `/tasks/${TASK_ID}` });

    await user.click(await screen.findByRole('button', { name: /Пробная проверка/ }));

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith(`/tasks/${TASK_ID}/check`, {
        code: DETAIL.solution_template,
      });
    });

    // Разбор по тест-кейсу показан
    expect(await screen.findByText(/Результат пробной проверки/)).toBeTruthy();
    expect(screen.getByText(/Положительные/)).toBeTruthy();
    // Счётчик попыток на карточке задачи не изменился
    expect(screen.getByText(/Попыток: 0/)).toBeTruthy();
    // Кнопка «Спросить ассистента» есть и на странице результатов
    expect(
      screen.getAllByRole('link', { name: 'Спросить ассистента' }),
    ).toHaveLength(2);
  });
});
