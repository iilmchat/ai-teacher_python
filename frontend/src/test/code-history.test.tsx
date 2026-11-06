import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { CodePage } from '@/pages/CodePage';
import type { ExecutionRecord, SandboxLimits } from '@/types/api';
import { jsonResponse } from '@/test/utils';

const LIMITS: SandboxLimits = {
  timeout_seconds: 5,
  memory_limit_mb: 128,
  max_output_chars: 10_000,
  max_concurrency: 4,
  queue_timeout_seconds: 10,
  max_code_length: 20_000,
  allowed_modules: ['math', 'random'],
};

function makeRecord(index: number): ExecutionRecord {
  return {
    id: `00000000-0000-0000-0000-${String(index).padStart(12, '0')}`,
    code: `print(${index})`,
    output: `${index}\n`,
    error: null,
    success: true,
    execution_time: 0.01,
    created_at: '2026-11-06T10:00:00',
  };
}

const HISTORY: ExecutionRecord[] = [
  {
    id: '11111111-1111-1111-1111-111111111111',
    code: 'print("old")',
    output: 'old\n',
    error: null,
    success: true,
    execution_time: 0.123,
    created_at: '2026-11-06T10:00:00',
  },
  {
    id: '22222222-2222-2222-2222-222222222222',
    code: 'print(1 / 0)',
    output: '',
    error: 'ZeroDivisionError: division by zero',
    success: false,
    execution_time: 0.004,
    created_at: '2026-11-06T09:00:00',
  },
];

/** Заглушка API: лимиты и история; остальные запросы считаются ошибкой */
function stubApi(history: () => Response | Promise<Response>) {
  const requests: string[] = [];
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL): Promise<Response> => {
      const url = String(input);
      requests.push(url);

      if (url.endsWith('/code/limits')) {
        return jsonResponse(LIMITS);
      }
      if (url.includes('/code/history')) {
        return history();
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

describe('история запусков (S44-002)', () => {
  it('загружает список и раскрывает код, вывод и ошибку', async () => {
    const user = userEvent.setup();
    const { requests } = stubApi(() => jsonResponse(HISTORY));
    renderPage();

    expect(await screen.findByText('История запусков')).toBeInTheDocument();
    expect(await screen.findByText('print("old")')).toBeInTheDocument();
    expect(screen.getByText('Успех')).toBeInTheDocument();
    expect(screen.getByText('0.123 с')).toBeInTheDocument();
    expect(
      screen.getByText('ZeroDivisionError: division by zero'),
    ).toBeInTheDocument();

    const historyRequest = requests.find((url) => url.includes('/code/history'));
    expect(historyRequest).toContain('skip=0');
    expect(historyRequest).toContain('limit=11');

    const first = screen.getAllByTestId('code-history-item')[0];
    expect(first.querySelector('details')).not.toHaveAttribute('open');
    await user.click(within(first).getByText('Успех'));
    expect(first.querySelector('details')).toHaveAttribute('open');
  });

  it('возвращает код записи в редактор по кнопке «Запустить снова»', async () => {
    const user = userEvent.setup();
    stubApi(() => jsonResponse(HISTORY));
    renderPage();

    await screen.findByTestId('monaco-mock');
    const second = screen.getAllByTestId('code-history-item')[1];

    await user.click(
      within(second).getByRole('button', { name: 'Запустить снова' }),
    );

    expect(screen.getByTestId('monaco-mock')).toHaveValue('print(1 / 0)');
  });

  it('показывает ошибку сети и повторяет загрузку', async () => {
    const user = userEvent.setup();
    let fail = true;
    stubApi(() => {
      if (fail) {
        fail = false;
        return Promise.reject(new TypeError('network error'));
      }
      return jsonResponse([HISTORY[0]]);
    });
    renderPage();

    expect(
      await screen.findByText('Не удалось загрузить историю запусков'),
    ).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Повторить' }));

    expect(await screen.findByText('print("old")')).toBeInTheDocument();
  });

  it('догружает следующую страницу по кнопке «Показать ещё»', async () => {
    const user = userEvent.setup();
    let call = 0;
    const { requests } = stubApi(() => {
      call += 1;
      return jsonResponse(
        call === 1
          ? Array.from({ length: 11 }, (_, index) => makeRecord(index))
          : [makeRecord(10)],
      );
    });
    renderPage();

    expect(await screen.findAllByTestId('code-history-item')).toHaveLength(10);

    await user.click(screen.getByRole('button', { name: 'Показать ещё' }));

    await waitFor(() => {
      expect(screen.getAllByTestId('code-history-item')).toHaveLength(11);
    });
    expect(
      screen.queryByRole('button', { name: 'Показать ещё' }),
    ).not.toBeInTheDocument();
    expect(
      requests.filter((url) => url.includes('/code/history')),
    ).toHaveLength(2);
    expect(requests.at(-1)).toContain('skip=10');
  });
});
