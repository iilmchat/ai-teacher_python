import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { api } from '@/lib/api';
import { TaskDetailPage } from '@/pages/TaskDetailPage';
import { useTasksStore } from '@/store/tasks';
import { renderWithRouter } from '@/test/utils';
import type { AttemptList, SubmitResponse, TaskDetail } from '@/types/api';

const TASK_ID = '77777777-7777-7777-7777-777777777777';

const BASE_DETAIL: TaskDetail = {
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

const EMPTY_ATTEMPTS: AttemptList = { items: [], total: 0 };

const SUBMIT: SubmitResponse = {
  passed: false,
  passed_count: 0,
  total_count: 2,
  attempts: 1,
  status: 'in_progress',
  results: [],
  message: 'Пройдено 0 из 2 тестов.',
};

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

function resetStore(): void {
  useTasksStore.setState({
    tasks: [],
    detail: null,
    progress: null,
    submission: null,
    checkResult: null,
    attempts: null,
    attemptDetail: null,
    draftSavedAt: null,
    draftSaving: false,
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

/** Мок API: карточка задачи + пустая история попыток */
function mockApi(detail: TaskDetail) {
  vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
    if (path.endsWith('/attempts')) {
      return EMPTY_ATTEMPTS;
    }
    return detail;
  });
}

describe('TaskDetailPage — черновик (S42-003)', () => {
  beforeEach(() => {
    resetStore();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('восстанавливает черновик вместо шаблона', async () => {
    mockApi({
      ...BASE_DETAIL,
      draft_code: 'print("черновик")',
      draft_updated_at: '2026-11-05T10:00:00',
    });

    renderWithRouter(<TaskDetailPage />, { route: `/tasks/${TASK_ID}` });

    const editor = (await screen.findByTestId('code-input')) as HTMLTextAreaElement;
    expect(editor.value).toBe('print("черновик")');
  });

  it('показывает индикатор сохранения черновика', async () => {
    mockApi({
      ...BASE_DETAIL,
      draft_code: 'print(1)',
      draft_updated_at: '2026-11-05T10:00:00',
    });

    renderWithRouter(<TaskDetailPage />, { route: `/tasks/${TASK_ID}` });

    expect(await screen.findByText(/Черновик сохранён в/)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Удалить черновик' })).toBeTruthy();
  });

  it('сохраняет черновик после паузы в наборе', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockApi(BASE_DETAIL);
    const patch = vi.spyOn(api, 'patch').mockResolvedValue({
      has_draft: true,
      updated_at: '2026-11-05T10:05:00',
    });

    renderWithRouter(<TaskDetailPage />, { route: `/tasks/${TASK_ID}` });

    const editor = await screen.findByTestId('code-input');
    fireEvent.change(editor, { target: { value: 'print(42)' } });

    // До истечения паузы запрос не уходит
    expect(patch).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(900);

    expect(patch).toHaveBeenCalledWith(`/tasks/${TASK_ID}/draft`, {
      code: 'print(42)',
    });
  });

  it('очищает черновик по кнопке', async () => {
    const user = userEvent.setup();
    mockApi({
      ...BASE_DETAIL,
      draft_code: 'print(1)',
      draft_updated_at: '2026-11-05T10:00:00',
    });
    const remove = vi
      .spyOn(api, 'delete')
      .mockResolvedValue({ has_draft: false, updated_at: null });

    renderWithRouter(<TaskDetailPage />, { route: `/tasks/${TASK_ID}` });

    await user.click(await screen.findByRole('button', { name: 'Удалить черновик' }));

    await waitFor(() => {
      expect(remove).toHaveBeenCalledWith(`/tasks/${TASK_ID}/draft`);
    });
    await waitFor(() => {
      expect(screen.queryByText(/Черновик сохранён в/)).toBeNull();
    });
  });

  it('после отправки черновик считается сохранённым заново', async () => {
    const user = userEvent.setup();
    mockApi({
      ...BASE_DETAIL,
      draft_code: 'print(1)',
      draft_updated_at: '2026-11-05T10:00:00',
    });
    vi.spyOn(api, 'post').mockResolvedValue(SUBMIT);
    vi.spyOn(api, 'patch').mockResolvedValue({
      has_draft: true,
      updated_at: '2026-11-05T10:05:00',
    });

    renderWithRouter(<TaskDetailPage />, { route: `/tasks/${TASK_ID}` });

    await user.click(
      await screen.findByRole('button', { name: 'Отправить решение' }),
    );

    // Решение засчитано — сервер очистил черновик, индикатор исчезает
    await waitFor(() => {
      expect(screen.queryByText(/Черновик сохранён в/)).toBeNull();
    });
  });
});
