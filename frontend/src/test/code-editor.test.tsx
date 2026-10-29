import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { CodeEditor } from '@/components/code-editor/CodeEditor';
import { OutputPanel } from '@/components/code-editor/OutputPanel';
import type { ExecutionResult } from '@/types/api';

const RESULT: ExecutionResult = {
  success: true,
  output: '10\n',
  error: null,
  error_type: null,
  execution_time: 0.012,
  violations: [],
};

describe('CodeEditor', () => {
  it('показывает начальный код', () => {
    render(<CodeEditor value="print(1)" onChange={vi.fn()} />);

    expect(screen.getByTestId('monaco-mock')).toHaveValue('print(1)');
  });

  it('сообщает об изменениях', async () => {
    const onChange = vi.fn();
    render(<CodeEditor value="" onChange={onChange} />);

    await userEvent.type(screen.getByTestId('monaco-mock'), 'x');

    expect(onChange).toHaveBeenCalled();
  });
});

describe('OutputPanel', () => {
  it('показывает пустое состояние', () => {
    render(<OutputPanel result={null} />);

    expect(screen.getByText('Пока пусто')).toBeInTheDocument();
  });

  it('показывает индикатор выполнения', () => {
    render(<OutputPanel result={null} running />);

    expect(screen.getByText('Выполняется…')).toBeInTheDocument();
  });

  it('показывает вывод и время выполнения', () => {
    render(<OutputPanel result={RESULT} />);

    expect(screen.getByLabelText('Результат')).toHaveTextContent('10');
    expect(screen.getByText(/0\.012/)).toBeInTheDocument();
  });

  it('показывает ошибку выполнения', () => {
    render(
      <OutputPanel
        result={{ ...RESULT, success: false, error: 'ZeroDivisionError', output: '' }}
      />,
    );

    expect(screen.getByRole('alert')).toHaveTextContent('ZeroDivisionError');
  });

  it('показывает нарушения песочницы', () => {
    render(
      <OutputPanel
        result={{
          ...RESULT,
          success: false,
          violations: ['Импорт запрещённого модуля: os'],
        }}
      />,
    );

    expect(screen.getByRole('alert')).toHaveTextContent('os');
  });

  it('показывает замечания линтера', () => {
    render(
      <OutputPanel
        result={RESULT}
        issues={[
          {
            line: 2,
            column: 3,
            code: 'W002',
            message: 'Сравнение с None',
            severity: 'warning',
          },
        ]}
      />,
    );

    expect(screen.getByText(/W002/)).toBeInTheDocument();
  });
});
