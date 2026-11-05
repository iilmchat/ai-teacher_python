import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { SessionList } from '@/components/chat/SessionList';
import type { ChatSession } from '@/types/api';

function session(overrides: Partial<ChatSession> = {}): ChatSession {
  return {
    id: 's1',
    user_id: 'u1',
    level: 'basic',
    title: 'Первый вопрос',
    pinned: false,
    created_at: '2026-11-01T10:00:00',
    updated_at: '2026-11-01T10:00:00',
    ...overrides,
  };
}

function renderList(sessions: ChatSession[], overrides: Partial<{
  onOpen: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onTogglePin: (id: string, pinned: boolean) => void;
  onDelete: (id: string) => void;
}> = {}) {
  const handlers = {
    onOpen: vi.fn(),
    onRename: vi.fn(),
    onTogglePin: vi.fn(),
    onDelete: vi.fn(),
    ...overrides,
  };
  render(<SessionList sessions={sessions} activeId={null} {...handlers} />);
  return handlers;
}

describe('SessionList (S43-001)', () => {
  it('показывает заголовок и индикатор закрепления', () => {
    renderList([
      session({ id: 's1', title: 'Цикл for', pinned: true }),
      session({ id: 's2', title: null }),
    ]);

    expect(screen.getByText('Цикл for')).toBeInTheDocument();
    expect(screen.getByLabelText('Закреплён')).toBeInTheDocument();
    expect(screen.getByText('Без названия')).toBeInTheDocument();
  });

  it('переименовывает сессию по Enter', async () => {
    const user = userEvent.setup();
    const handlers = renderList([session()]);

    await user.click(
      screen.getByRole('button', { name: 'Переименовать чат: Первый вопрос' }),
    );
    const input = screen.getByLabelText('Название чата');
    await user.clear(input);
    await user.type(input, 'Новое имя{Enter}');

    expect(handlers.onRename).toHaveBeenCalledWith('s1', 'Новое имя');
  });

  it('отменяет переименование по Escape', async () => {
    const user = userEvent.setup();
    const handlers = renderList([session()]);

    await user.click(
      screen.getByRole('button', { name: 'Переименовать чат: Первый вопрос' }),
    );
    await user.type(screen.getByLabelText('Название чата'), 'другое{Escape}');

    expect(handlers.onRename).not.toHaveBeenCalled();
    expect(screen.queryByLabelText('Название чата')).not.toBeInTheDocument();
  });

  it('не сохраняет пустой заголовок', async () => {
    const user = userEvent.setup();
    const handlers = renderList([session()]);

    await user.click(
      screen.getByRole('button', { name: 'Переименовать чат: Первый вопрос' }),
    );
    await user.clear(screen.getByLabelText('Название чата'));
    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    expect(handlers.onRename).not.toHaveBeenCalled();
  });

  it('переключает закрепление', async () => {
    const user = userEvent.setup();
    const handlers = renderList([session()]);

    await user.click(
      screen.getByRole('button', { name: 'Закрепить чат: Первый вопрос' }),
    );

    expect(handlers.onTogglePin).toHaveBeenCalledWith('s1', true);
  });

  it('удаляет только после подтверждения', async () => {
    const user = userEvent.setup();
    const handlers = renderList([session()]);
    const confirm = vi.spyOn(window, 'confirm');

    confirm.mockReturnValueOnce(false);
    await user.click(
      screen.getByRole('button', { name: 'Удалить чат: Первый вопрос' }),
    );
    expect(handlers.onDelete).not.toHaveBeenCalled();

    confirm.mockReturnValueOnce(true);
    await user.click(
      screen.getByRole('button', { name: 'Удалить чат: Первый вопрос' }),
    );
    expect(handlers.onDelete).toHaveBeenCalledWith('s1');
    expect(confirm).toHaveBeenCalledWith(
      'Удалить чат «Первый вопрос»? Это действие нельзя отменить.',
    );
  });
});
