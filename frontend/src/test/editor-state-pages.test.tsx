import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { api } from '@/lib/api';
import {
  editorStateKey,
  readEditorState,
  taskEditorContext,
  writeEditorState,
} from '@/lib/editorState';
import { CodePage } from '@/pages/CodePage';
import { TaskDetailPage } from '@/pages/TaskDetailPage';
import { useTasksStore } from '@/store/tasks';
import { renderWithRouter } from '@/test/utils';
import type { AttemptList, SandboxLimits, SubmitResponse, TaskDetail } from '@/types/api';

const TASK_ID = '77777777-7777-7777-7777-777777777777';

const LIMITS: SandboxLimits = {
  timeout_seconds: 5,
  memory_limit_mb: 128,
  max_output_chars: 10_000,
  max_concurrency: 4,
  queue_timeout_seconds: 10,
  max_code_length: 20_000,
  allowed_modules: ['math', 'random'],
};

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

vi.mock('@/components/code-editor/CodeEditor', () => ({
  CodeEditor: ({ value, onChange }: { value: string; onChange: (value: string) => void }) => (
    <textarea
      data-testid="code-input"
      aria-label="Редактор кода"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  ),
}));

function resetTasksStore(): void {
  useTasksStore.setState({
    tasks: [],
    detail: null,
    progress: null,
    submission: null,
    checkResult: null,
    attempts: null,
    attemptDetail: null,
    recommended: null,
    draftSavedAt: null,
    draftSaving: false,
    filters: {
      difficulty: null,
      category: null,
      tag: null,
      status: null,
      search: '',
    },
    found: 0,
    loading: false,
    submitting: false,
    checking: false,
    error: null,
  });
}

function mockSandboxApi(): void {
  vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
    if (path.endsWith('/code/limits')) {
      return LIMITS;
    }
    if (path.includes('/code/history')) {
      return [];
    }
    throw new Error(`Неожиданный запрос: ${path}`);
  });
}

function mockTaskApi(detail: TaskDetail): void {
  vi.spyOn(api, 'get').mockImplementation(async (path: string) => {
    if (path.endsWith('/attempts')) {
      return EMPTY_ATTEMPTS;
    }
    return detail;
  });
}

describe('песочница: сохранение состояния (S44-004)', () => {
  beforeEach(() => {
    mockSandboxApi();
  });

  it('восстанавливает код после перезагрузки', async () => {
    writeEditorState('code', 'print("saved")', Date.now() - 1_000);

    render(
      <MemoryRouter>
        <CodePage />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('code-input')).toHaveValue('print("saved")');
  });

  it('очищает сохранённый код по кнопке', async () => {
    const user = userEvent.setup();
    writeEditorState('code', 'print("saved")', Date.now() - 1_000);

    render(
      <MemoryRouter>
        <CodePage />
      </MemoryRouter>,
    );

    await user.click(await screen.findByRole('button', { name: 'Очистить сохранённое' }));

    expect(readEditorState('code')).toBeNull();
    expect(localStorage.getItem(editorStateKey('code'))).toBeNull();
    expect(screen.queryByRole('button', { name: 'Очистить сохранённое' })).not.toBeInTheDocument();
  });

  it('не записывает загруженный .py до правки', async () => {
    const user = userEvent.setup({ applyAccept: false });

    render(
      <MemoryRouter>
        <CodePage />
      </MemoryRouter>,
    );
    await screen.findByTestId('code-input');

    await user.upload(
      screen.getByTestId('code-file-input'),
      new File(['print("file")\n'], 'task.py', { type: 'text/x-python' }),
    );

    expect(await screen.findByTestId('code-input')).toHaveValue('print("file")\n');
    expect(readEditorState('code')).toBeNull();
  });

  it('предупреждает, если сохранённый код новее файла', async () => {
    const user = userEvent.setup({ applyAccept: false });
    const now = Date.now();
    writeEditorState('code', 'print("saved")', now - 60_000);

    render(
      <MemoryRouter>
        <CodePage />
      </MemoryRouter>,
    );

    const editor = await screen.findByTestId('code-input');
    await user.upload(
      screen.getByTestId('code-file-input'),
      new File(['print("file")\n'], 'old.py', {
        type: 'text/x-python',
        lastModified: now - 120_000,
      }),
    );

    expect(await screen.findByText(/Сохранённый черновик новее файла/)).toBeInTheDocument();
    expect(editor).toHaveValue('print("saved")');

    await user.click(screen.getByRole('button', { name: 'Загрузить файл' }));

    expect(editor).toHaveValue('print("file")\n');
    expect(readEditorState('code')).toBeNull();
  });
});

describe('задача: сохранение состояния (S44-004)', () => {
  beforeEach(() => {
    resetTasksStore();
  });

  it('восстанавливает более новый локальный код и предупреждает', async () => {
    const now = Date.now();
    writeEditorState(taskEditorContext(TASK_ID), 'print("local")', now - 30_000);
    mockTaskApi({
      ...DETAIL,
      draft_code: 'print("server")',
      draft_updated_at: new Date(now - 60_000).toISOString(),
    });

    renderWithRouter(<TaskDetailPage />, { route: `/tasks/${TASK_ID}` });

    expect(await screen.findByTestId('code-input')).toHaveValue('print("local")');
    expect(screen.getByText(/более новый код, чем черновик на сервере/)).toBeInTheDocument();
  });

  it('предпочитает серверный черновик, если он новее локального', async () => {
    const now = Date.now();
    writeEditorState(taskEditorContext(TASK_ID), 'print("local")', now - 120_000);
    mockTaskApi({
      ...DETAIL,
      draft_code: 'print("server")',
      draft_updated_at: new Date(now - 60_000).toISOString(),
    });

    renderWithRouter(<TaskDetailPage />, { route: `/tasks/${TASK_ID}` });

    expect(await screen.findByTestId('code-input')).toHaveValue('print("server")');
    expect(screen.queryByText(/более новый код, чем черновик на сервере/)).not.toBeInTheDocument();
  });

  it('очищает локальное состояние по кнопке', async () => {
    const user = userEvent.setup();
    writeEditorState(taskEditorContext(TASK_ID), 'print("local")', Date.now() - 1_000);
    mockTaskApi(DETAIL);

    renderWithRouter(<TaskDetailPage />, { route: `/tasks/${TASK_ID}` });

    await user.click(await screen.findByRole('button', { name: 'Очистить сохранённое' }));

    expect(readEditorState(taskEditorContext(TASK_ID))).toBeNull();
  });

  it('не оставляет локальную копию после явной отправки', async () => {
    const user = userEvent.setup();
    writeEditorState(taskEditorContext(TASK_ID), 'print("local")', Date.now() - 1_000);
    mockTaskApi(DETAIL);
    const post = vi.spyOn(api, 'post').mockResolvedValue(SUBMIT);

    renderWithRouter(<TaskDetailPage />, { route: `/tasks/${TASK_ID}` });

    await user.click(await screen.findByRole('button', { name: 'Отправить решение' }));

    await waitFor(() => {
      expect(post).toHaveBeenCalledWith(`/tasks/${TASK_ID}/submit`, {
        code: 'print("local")',
      });
    });
    await waitFor(() => {
      expect(readEditorState(taskEditorContext(TASK_ID))).toBeNull();
    });
  });
});
