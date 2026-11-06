import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { CodePage } from '@/pages/CodePage';
import { MAX_CODE_FILE_BYTES, MAX_CODE_LENGTH } from '@/lib/codeFiles';
import { useAuthStore } from '@/store/auth';
import type { SandboxLimits, User } from '@/types/api';
import { jsonResponse } from '@/test/utils';

const LIMITS: SandboxLimits = {
  timeout_seconds: 5,
  memory_limit_mb: 128,
  max_output_chars: 10_000,
  max_concurrency: 4,
  queue_timeout_seconds: 10,
  max_code_length: MAX_CODE_LENGTH,
  allowed_modules: ['math', 'random'],
};

function makeUser(settings: Record<string, unknown> = {}): User {
  return {
    id: '11111111-1111-1111-1111-111111111111',
    email: 'student@example.com',
    username: 'student',
    role: 'student',
    level: 'basic',
    created_at: '2026-11-06T10:00:00',
    last_active: '2026-11-06T10:00:00',
    settings,
  };
}

interface StubbedRequest {
  url: string;
  method?: string;
  body?: unknown;
}

/** Заглушка API песочницы и настроек профиля */
function stubApi() {
  const requests: StubbedRequest[] = [];
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const url = String(input);
      requests.push({
        url,
        method: init?.method,
        body: typeof init?.body === 'string' ? JSON.parse(init.body) : undefined,
      });

      if (url.endsWith('/code/limits')) {
        return jsonResponse(LIMITS);
      }
      if (url.includes('/code/history')) {
        return jsonResponse([]);
      }
      if (url.endsWith('/users/me/settings')) {
        const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
        const user = useAuthStore.getState().user ?? makeUser();
        return jsonResponse({
          ...user,
          settings: { ...user.settings, ...body },
        });
      }
      throw new Error(`Неожиданный запрос: ${url}`);
    },
  );

  vi.stubGlobal('fetch', fetchMock);
  return { requests };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <CodePage />
    </MemoryRouter>,
  );
}

let createdBlobs: Blob[];

beforeEach(() => {
  useAuthStore.setState({
    user: makeUser(),
    initializing: false,
    loading: false,
    error: null,
  });

  createdBlobs = [];
  Object.defineProperty(URL, 'createObjectURL', {
    configurable: true,
    value: vi.fn((blob: Blob) => {
      createdBlobs.push(blob);
      return 'blob:mock';
    }),
  });
  Object.defineProperty(URL, 'revokeObjectURL', {
    configurable: true,
    value: vi.fn(),
  });
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});

async function uploadFile(file: File) {
  // Отключаем фильтр `accept`: отказ по расширению проверяет приложение,
  // иначе userEvent не доставит не-.py файл до обработчика.
  const user = userEvent.setup({ applyAccept: false });
  await user.upload(screen.getByTestId('code-file-input'), file);
}

describe('файлы песочницы (S44-003)', () => {
  it('скачивает текущий код как code.py', async () => {
    const user = userEvent.setup();
    stubApi();
    renderPage();

    const editor = await screen.findByTestId('monaco-mock');
    fireEvent.change(editor, { target: { value: 'print("download")' } });

    await user.click(screen.getByRole('button', { name: 'Скачать .py' }));

    expect(createdBlobs).toHaveLength(1);
    expect(await createdBlobs[0].text()).toBe('print("download")');
  });

  it('загружает .py и заменяет код в редакторе', async () => {
    stubApi();
    renderPage();
    await screen.findByTestId('monaco-mock');

    await uploadFile(
      new File(['print(42)\n'], 'task.py', { type: 'text/x-python' }),
    );

    await waitFor(() => {
      expect(screen.getByTestId('monaco-mock')).toHaveValue('print(42)\n');
    });
    // Загруженный файл не становится черновиком до явного действия (S44-004).
    expect(localStorage.getItem('ai-teacher.code.draft')).toBeNull();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('отказывает файлу не-.py и не трогает редактор', async () => {
    stubApi();
    renderPage();
    const editor = await screen.findByTestId('monaco-mock');
    const before = (editor as HTMLTextAreaElement).value;

    await uploadFile(new File(['print(1)'], 'task.txt', { type: 'text/plain' }));

    expect(
      await screen.findByText('Можно загрузить только файл с расширением .py'),
    ).toBeInTheDocument();
    expect(editor).toHaveValue(before);
  });

  it('отказывает файлу больше 200 КБ', async () => {
    stubApi();
    renderPage();
    await screen.findByTestId('monaco-mock');

    await uploadFile(
      new File(['x'.repeat(MAX_CODE_FILE_BYTES + 1)], 'big.py', {
        type: 'text/x-python',
      }),
    );

    expect(await screen.findByText('Файл больше 200 КБ')).toBeInTheDocument();
  });

  it('отказывает коду длиннее 20 000 символов', async () => {
    stubApi();
    renderPage();
    await screen.findByTestId('monaco-mock');

    await uploadFile(
      new File(['x'.repeat(MAX_CODE_LENGTH + 1)], 'long.py', {
        type: 'text/x-python',
      }),
    );

    expect(
      await screen.findByText('Код длиннее 20 000 символов'),
    ).toBeInTheDocument();
  });
});

describe('сниппеты кода (S44-003)', () => {
  it('сохраняет, применяет и удаляет сниппет через настройки профиля', async () => {
    const user = userEvent.setup();
    const { requests } = stubApi();
    renderPage();

    const editor = await screen.findByTestId('monaco-mock');
    fireEvent.change(editor, { target: { value: 'print("snippet")' } });

    await user.click(
      screen.getByRole('button', { name: 'Сохранить как сниппет' }),
    );
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByLabelText('Название'), 'Печать');
    await user.click(within(dialog).getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => {
      const patch = requests
        .filter((request) => request.url.endsWith('/users/me/settings'))
        .at(-1);
      expect(patch?.body).toEqual({
        snippets: [
          {
            id: expect.any(String),
            name: 'Печать',
            code: 'print("snippet")',
          },
        ],
      });
    });
    expect(await screen.findByText('Печать')).toBeInTheDocument();
    expect(useAuthStore.getState().user?.settings.snippets).toHaveLength(1);

    fireEvent.change(editor, { target: { value: 'print("changed")' } });
    const item = screen.getByTestId('code-snippet-item');
    await user.click(within(item).getByRole('button', { name: 'Применить' }));
    expect(editor).toHaveValue('print("snippet")');

    vi.spyOn(window, 'confirm').mockReturnValue(true);
    await user.click(
      within(screen.getByTestId('code-snippet-item')).getByRole('button', {
        name: 'Удалить',
      }),
    );

    await waitFor(() => {
      expect(screen.queryAllByTestId('code-snippet-item')).toHaveLength(0);
    });
    expect(screen.getByText(/Сниппетов пока нет/)).toBeInTheDocument();

    const patches = requests.filter((request) =>
      request.url.endsWith('/users/me/settings'),
    );
    expect(patches.at(-1)?.body).toEqual({ snippets: [] });
  });

  it('показывает лимит и не даёт сохранить 21-й сниппет', async () => {
    const settings = {
      snippets: Array.from({ length: 20 }, (_, index) => ({
        id: `snippet-${index}`,
        name: `Сниппет ${index}`,
        code: `print(${index})`,
      })),
    };
    useAuthStore.setState({ user: makeUser(settings) });
    stubApi();
    renderPage();

    expect(await screen.findByText('20 из 20')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Сохранить как сниппет' }),
    ).toBeDisabled();
    expect(
      screen.getByText(
        'Достигнут лимит: можно сохранить не больше 20 сниппетов.',
      ),
    ).toBeInTheDocument();
  });

  it('не открывает сохранение, если редактор пуст', async () => {
    stubApi();
    renderPage();

    const editor = await screen.findByTestId('monaco-mock');
    fireEvent.change(editor, { target: { value: '   ' } });

    expect(
      screen.getByRole('button', { name: 'Сохранить как сниппет' }),
    ).toBeDisabled();
  });
});
