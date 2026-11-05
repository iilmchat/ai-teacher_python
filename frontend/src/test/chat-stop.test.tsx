import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { api } from '@/lib/api';
import { ChatPage } from '@/pages/ChatPage';
import { useChatStore } from '@/store/chat';
import { renderWithRouter } from '@/test/utils';
import type { ChatSessionWithMessages } from '@/types/api';

const { stopMock } = vi.hoisted(() => ({ stopMock: vi.fn() }));

vi.mock('@/lib/chatSocket', () => ({
  openChatSocket: () => ({
    send: () => true,
    stop: stopMock,
    close: () => undefined,
    ready: true,
  }),
}));

const SESSION: ChatSessionWithMessages = {
  id: '55555555-5555-5555-5555-555555555555',
  user_id: '11111111-1111-1111-1111-111111111111',
  level: 'basic',
  title: 'Вопрос про цикл',
  pinned: false,
  created_at: '2026-11-01T10:00:00',
  updated_at: '2026-11-01T10:00:00',
  messages: [
    {
      id: 'm1',
      session_id: '55555555-5555-5555-5555-555555555555',
      role: 'assistant',
      content: 'Ответ ассистента',
      code_blocks: [],
      created_at: '2026-11-01T10:01:00',
    },
  ],
};

function resetStore(): void {
  useChatStore.setState({
    sessions: [SESSION],
    active: SESSION,
    draft: '',
    streaming: false,
    loading: false,
    error: null,
    taskContext: null,
  });
}

describe('ChatPage: остановка и регенерация (S43-002)', () => {
  beforeEach(() => {
    resetStore();
    stopMock.mockClear();
    vi.restoreAllMocks();
    vi.spyOn(api, 'get').mockResolvedValue([SESSION]);
  });

  it('показывает «Стоп» во время стриминга и останавливает генерацию', async () => {
    const user = userEvent.setup();
    useChatStore.setState({ streaming: true });

    renderWithRouter(<ChatPage />, { route: '/chat' });

    const button = screen.getByRole('button', { name: 'Стоп' });
    await user.click(button);

    expect(stopMock).toHaveBeenCalled();
  });

  it('не показывает «Стоп», когда генерации нет', () => {
    renderWithRouter(<ChatPage />, { route: '/chat' });

    expect(screen.queryByRole('button', { name: 'Стоп' })).not.toBeInTheDocument();
  });

  it('перегенерирует ответ по кнопке «Повторить»', async () => {
    const user = userEvent.setup();
    const post = vi.spyOn(api, 'post').mockResolvedValue({
      ...SESSION.messages[0],
      id: 'm2',
      content: 'Новый ответ',
    });

    renderWithRouter(<ChatPage />, { route: '/chat' });

    await user.click(screen.getByRole('button', { name: 'Повторить' }));

    expect(post).toHaveBeenCalledWith(
      `/chat/sessions/${SESSION.id}/messages/${SESSION.messages[0].id}/regenerate`,
    );
  });
});
