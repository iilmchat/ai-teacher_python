import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { ChatSearchPanel } from '@/components/chat/ChatSearchPanel';
import { api } from '@/lib/api';

vi.mock('@/lib/api', () => ({
  api: { get: vi.fn() },
}));

const getMock = vi.mocked(api.get);

afterEach(() => {
  vi.clearAllMocks();
});

describe('ChatSearchPanel (S27-003)', () => {
  it('показывает результаты с подсветкой и открывает сессию', async () => {
    getMock.mockResolvedValue({
      query: 'цикл',
      mode: 'ilike',
      total: 1,
      items: [
        {
          id: 'm1',
          session_id: 's1',
          role: 'assistant',
          content: 'Цикл for перебирает элементы',
          created_at: '2026-10-31T10:00:00',
        },
      ],
    });
    const onOpenSession = vi.fn();

    render(<ChatSearchPanel onOpenSession={onOpenSession} />);
    await userEvent.type(screen.getByLabelText('Поисковый запрос'), 'цикл');
    await userEvent.click(screen.getByRole('button', { name: 'Найти' }));

    await waitFor(() => expect(screen.getByRole('mark')).toHaveTextContent('Цикл'));
    expect(screen.getByText(/Найдено: 1/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Цикл for/ }));
    expect(onOpenSession).toHaveBeenCalledWith('s1');
    expect(getMock).toHaveBeenCalledWith('/chat/search?q=%D1%86%D0%B8%D0%BA%D0%BB&limit=10');
  });

  it('показывает пустое состояние', async () => {
    getMock.mockResolvedValue({ query: 'нет', mode: 'ilike', total: 0, items: [] });

    render(<ChatSearchPanel onOpenSession={vi.fn()} />);
    await userEvent.type(screen.getByLabelText('Поисковый запрос'), 'нет');
    await userEvent.click(screen.getByRole('button', { name: 'Найти' }));

    await waitFor(() =>
      expect(screen.getByText('Ничего не найдено — попробуйте другие слова')).toBeInTheDocument(),
    );
  });

  it('показывает ошибку и не падает', async () => {
    getMock.mockRejectedValue(new Error('boom'));

    render(<ChatSearchPanel onOpenSession={vi.fn()} />);
    await userEvent.type(screen.getByLabelText('Поисковый запрос'), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Найти' }));

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('Поиск недоступен'),
    );
  });

  it('aria-live сообщает о загрузке', async () => {
    let resolve: (value: unknown) => void = () => undefined;
    getMock.mockImplementation(
      () => new Promise((r) => { resolve = r; }) as never,
    );

    render(<ChatSearchPanel onOpenSession={vi.fn()} />);
    await userEvent.type(screen.getByLabelText('Поисковый запрос'), 'x');
    await userEvent.click(screen.getByRole('button', { name: 'Найти' }));

    expect(screen.getByText('Ищем…')).toBeInTheDocument();
    resolve({ query: 'x', mode: 'ilike', total: 0, items: [] });
    await waitFor(() => expect(screen.queryByText('Ищем…')).not.toBeInTheDocument());
  });
});
