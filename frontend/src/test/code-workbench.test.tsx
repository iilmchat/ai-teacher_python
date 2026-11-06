import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { CodePage } from '@/pages/CodePage';
import type {
  AnalyzeResponse,
  ExecutionResult,
  LintResponse,
  SandboxLimits,
} from '@/types/api';
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

const EXECUTION: ExecutionResult = {
  success: true,
  output: 'Привет, Аня!\n',
  error: null,
  error_type: null,
  execution_time: 0.012,
  violations: [],
};

const LINT: LintResponse = {
  issues: [],
  errors: 0,
  warnings: 0,
  infos: 0,
};

const ANALYSIS: AnalyzeResponse = {
  issues: [
    {
      line: 2,
      column: 1,
      code: 'W002',
      message: 'Сравнение с None',
      severity: 'warning',
    },
  ],
  stats: {
    lines: 3,
    functions: 0,
    classes: 0,
    loops: 0,
    conditions: 1,
    imports: 0,
  },
  summary: 'Код рабочий, но есть 1 замечание по стилю.',
};

interface StubbedRequest {
  url: string;
  body: unknown;
}

/** Заглушка HTTP API: CodePage ходит в limits, execute, lint и analyze */
function stubApi() {
  const requests: StubbedRequest[] = [];
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const url = String(input);
      requests.push({
        url,
        body: typeof init?.body === 'string' ? JSON.parse(init.body) : undefined,
      });

      if (url.endsWith('/code/limits')) {
        return jsonResponse(LIMITS);
      }
      if (url.endsWith('/code/execute')) {
        return jsonResponse(EXECUTION);
      }
      if (url.endsWith('/code/lint')) {
        return jsonResponse(LINT);
      }
      if (url.endsWith('/code/analyze')) {
        return jsonResponse(ANALYSIS);
      }
      throw new Error(`Неожиданный запрос: ${url}`);
    },
  );

  vi.stubGlobal('fetch', fetchMock);
  return { fetchMock, requests };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <CodePage />
    </MemoryRouter>,
  );
}

describe('CodePage: stdin, лимиты и разбор (S44-001)', () => {
  it('передаёт введённый stdin в POST /code/execute', async () => {
    const user = userEvent.setup();
    const { requests } = stubApi();
    renderPage();

    await user.type(await screen.findByLabelText('Ввод (stdin)'), 'Аня');
    await user.click(screen.getByRole('button', { name: 'Запустить' }));

    await waitFor(() => {
      const execute = requests.find((request) => request.url.endsWith('/code/execute'));
      expect(execute?.body).toEqual({
        code: expect.stringContaining('input'),
        stdin: 'Аня',
      });
    });
    expect(await screen.findByLabelText('Результат')).toHaveTextContent('Привет, Аня!');
  });

  it('показывает лимиты песочницы в раскрывающейся секции', async () => {
    const user = userEvent.setup();
    stubApi();
    renderPage();

    const summary = await screen.findByText('Ограничения песочницы');
    expect(await screen.findByText('Таймаут: 5 с')).toBeInTheDocument();
    expect(screen.getByText('Память: 128 МБ')).toBeInTheDocument();
    expect(screen.getByText('Длина кода: до 20000 символов')).toBeInTheDocument();
    expect(screen.getByText('Разрешённые модули: math, random')).toBeInTheDocument();

    await user.click(summary);

    expect(summary.closest('details')).toHaveAttribute('open');
  });

  it('показывает сводку, метрики и замечания разбора', async () => {
    const user = userEvent.setup();
    const { requests } = stubApi();
    renderPage();

    await user.click(screen.getByRole('button', { name: 'Разобрать' }));

    expect(await screen.findByText(ANALYSIS.summary)).toBeInTheDocument();
    expect(screen.getByText('Предупреждения (1)')).toBeInTheDocument();
    expect(screen.getByText(/Сравнение с None/)).toBeInTheDocument();
    expect(screen.getByText('Строк: 3')).toBeInTheDocument();

    const analyze = requests.find((request) => request.url.endsWith('/code/analyze'));
    expect(analyze?.body).toEqual({ code: expect.stringContaining('input') });
  });
});
