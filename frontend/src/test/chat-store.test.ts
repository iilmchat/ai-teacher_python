import { beforeEach, describe, expect, it, vi } from 'vitest';

import { api } from '@/lib/api';
import { useChatStore } from '@/store/chat';
import type { ChatSession, ChatSessionWithMessages } from '@/types/api';

const SESSION: ChatSession = {
  id: '55555555-5555-5555-5555-555555555555',
  user_id: '11111111-1111-1111-1111-111111111111',
  level: 'basic',
  created_at: '2026-10-29T10:00:00',
  updated_at: '2026-10-29T10:00:00',
};

const SESSION_WITH_MESSAGES: ChatSessionWithMessages = {
  ...SESSION,
  messages: [
    {
      id: 'm1',
      session_id: SESSION.id,
      role: 'user',
      content: 'Почему код не работает?',
      code_blocks: [],
      created_at: '2026-10-29T10:01:00',
    },
  ],
};

function resetStore(): void {
  useChatStore.setState({
    sessions: [],
    active: null,
    draft: '',
    streaming: false,
    loading: false,
    error: null,
  });
}

describe('chat store', () => {
  beforeEach(() => {
    resetStore();
  });

  it('загружает список сессий', async () => {
    vi.spyOn(api, 'get').mockResolvedValue([SESSION]);

    await useChatStore.getState().loadSessions();

    expect(useChatStore.getState().sessions).toHaveLength(1);
    expect(useChatStore.getState().error).toBeNull();
  });

  it('создаёт сессию с выбранным уровнем', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue(SESSION);

    await useChatStore.getState().createSession('advanced');

    expect(post).toHaveBeenCalledWith('/chat/sessions', { level: 'advanced' });
    expect(useChatStore.getState().sessions[0].id).toBe(SESSION.id);
  });

  it('создаёт сессию без уровня, если он не задан', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue(SESSION);

    await useChatStore.getState().createSession();

    expect(post).toHaveBeenCalledWith('/chat/sessions', {});
  });

  it('открывает сессию с историей', async () => {
    useChatStore.setState({ loading: true });
    vi.spyOn(api, 'get').mockResolvedValue(SESSION_WITH_MESSAGES);

    await useChatStore.getState().openSession(SESSION.id);

    const state = useChatStore.getState();
    expect(state.active?.messages).toHaveLength(1);
    expect(state.loading).toBe(false);
  });

  it('оптимистично добавляет вопрос ученика', () => {
    useChatStore.setState({ active: { ...SESSION_WITH_MESSAGES, messages: [] } });

    useChatStore.getState().addUserMessage('Новый вопрос');

    const messages = useChatStore.getState().active?.messages ?? [];
    expect(messages).toHaveLength(1);
    expect(messages[0]).toMatchObject({ role: 'user', content: 'Новый вопрос' });
  });

  it('собирает ответ ассистента из токенов', () => {
    useChatStore.setState({ active: { ...SESSION_WITH_MESSAGES, messages: [] } });

    useChatStore.getState().startAssistantDraft();
    useChatStore.getState().appendToken('Попробуй ');
    useChatStore.getState().appendToken('проверить условие.');

    expect(useChatStore.getState().draft).toBe('Попробуй проверить условие.');
    expect(useChatStore.getState().streaming).toBe(true);

    useChatStore.getState().finishStream();

    const state = useChatStore.getState();
    expect(state.draft).toBe('');
    expect(state.streaming).toBe(false);
    expect(state.active?.messages.at(-1)).toMatchObject({
      role: 'assistant',
      content: 'Попробуй проверить условие.',
    });
  });

  it('финализирует стрим полным текстом от сервера', () => {
    useChatStore.setState({ active: { ...SESSION_WITH_MESSAGES, messages: [] } });
    useChatStore.getState().startAssistantDraft();
    useChatStore.getState().appendToken('частично');

    useChatStore.getState().finishStream('полный ответ');

    expect(useChatStore.getState().active?.messages.at(-1)?.content).toBe('полный ответ');
  });

  it('не добавляет пустой ответ ассистента', () => {
    useChatStore.setState({ active: { ...SESSION_WITH_MESSAGES, messages: [] } });
    useChatStore.getState().startAssistantDraft();

    useChatStore.getState().finishStream('   ');

    expect(useChatStore.getState().active?.messages).toHaveLength(0);
  });

  it('фиксирует ошибку стриминга', () => {
    useChatStore.getState().failStream('Требуется авторизация');

    expect(useChatStore.getState().error).toBe('Требуется авторизация');
    expect(useChatStore.getState().streaming).toBe(false);
  });

  it('REST-фолбэк добавляет ответ ассистента', async () => {
    useChatStore.setState({ active: { ...SESSION_WITH_MESSAGES, messages: [] } });
    useChatStore.getState().addUserMessage('вопрос');
    vi.spyOn(api, 'post').mockResolvedValue({
      user_message: SESSION_WITH_MESSAGES.messages[0],
      assistant_message: {
        id: 'a1',
        session_id: SESSION.id,
        role: 'assistant',
        content: 'ответ',
        code_blocks: [],
        created_at: '2026-10-29T10:02:00',
      },
    });

    await useChatStore.getState().sendViaRest('вопрос');

    const messages = useChatStore.getState().active?.messages ?? [];
    expect(messages).toHaveLength(2);
    expect(messages.at(-1)?.content).toBe('ответ');
  });

  it('удаляет сессию из списка и сбрасывает активную', async () => {
    useChatStore.setState({ sessions: [SESSION], active: SESSION_WITH_MESSAGES });
    vi.spyOn(api, 'delete').mockResolvedValue(undefined);

    await useChatStore.getState().deleteSession(SESSION.id);

    expect(useChatStore.getState().sessions).toHaveLength(0);
    expect(useChatStore.getState().active).toBeNull();
  });
});
