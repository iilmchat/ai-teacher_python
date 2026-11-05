import { beforeEach, describe, expect, it, vi } from 'vitest';

import { api } from '@/lib/api';
import { useChatStore } from '@/store/chat';
import type { ChatSession, ChatSessionWithMessages } from '@/types/api';

const SESSION: ChatSession = {
  id: '55555555-5555-5555-5555-555555555555',
  user_id: '11111111-1111-1111-1111-111111111111',
  level: 'basic',
  title: null,
  pinned: false,
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

const TASK_ID = '77777777-7777-7777-7777-777777777777';

function resetStore(): void {
  useChatStore.setState({
    sessions: [],
    active: null,
    draft: '',
    streaming: false,
    loading: false,
    error: null,
    taskContext: null,
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

  it('сохраняет предупреждения политики уровня в сообщении', () => {
    useChatStore.setState({ active: { ...SESSION_WITH_MESSAGES, messages: [] } });
    useChatStore.getState().startAssistantDraft();

    useChatStore.getState().finishStream('Вот решение', ['basic_full_solution']);

    expect(useChatStore.getState().active?.messages.at(-1)?.warnings).toEqual([
      'basic_full_solution',
    ]);
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

  it('первое сообщение задаёт авто-заголовок до 60 символов (S43-001)', () => {
    useChatStore.setState({
      sessions: [SESSION],
      active: { ...SESSION_WITH_MESSAGES, title: null, messages: [] },
    });

    useChatStore
      .getState()
      .addUserMessage('  Почему   мой код не работает? ' + 'очень длинный вопрос '.repeat(5));

    const state = useChatStore.getState();
    expect(state.active?.title).toMatch(/^Почему мой код не работает\?/);
    expect(state.active?.title?.length).toBeLessThanOrEqual(60);
    expect(state.sessions[0].title).toBe(state.active?.title);
  });

  it('не перезаписывает заголовок вторым сообщением (S43-001)', () => {
    useChatStore.setState({
      sessions: [SESSION],
      active: { ...SESSION_WITH_MESSAGES, title: 'Ручной заголовок', messages: [] },
    });

    useChatStore.getState().addUserMessage('Другой вопрос');

    expect(useChatStore.getState().active?.title).toBe('Ручной заголовок');
    expect(useChatStore.getState().sessions[0].title).toBe('Ручной заголовок');
  });

  it('переименовывает сессию через PATCH (S43-001)', async () => {
    const renamed = { ...SESSION, title: 'Разбор цикла for' };
    const patch = vi.spyOn(api, 'patch').mockResolvedValue(renamed);
    useChatStore.setState({ sessions: [SESSION], active: SESSION_WITH_MESSAGES });

    await useChatStore.getState().renameSession(SESSION.id, 'Разбор цикла for');

    expect(patch).toHaveBeenCalledWith(`/chat/sessions/${SESSION.id}`, {
      title: 'Разбор цикла for',
    });
    expect(useChatStore.getState().sessions[0].title).toBe('Разбор цикла for');
    expect(useChatStore.getState().active?.title).toBe('Разбор цикла for');
  });

  it('закрепляет сессию и поднимает её в начало списка (S43-001)', async () => {
    const other: ChatSession = {
      ...SESSION,
      id: '66666666-6666-6666-6666-666666666666',
      title: 'Свежий чат',
      updated_at: '2026-10-30T10:00:00',
    };
    const pinned = { ...SESSION, pinned: true };
    const patch = vi.spyOn(api, 'patch').mockResolvedValue(pinned);
    useChatStore.setState({ sessions: [other, SESSION] });

    await useChatStore.getState().togglePin(SESSION.id, true);

    expect(patch).toHaveBeenCalledWith(`/chat/sessions/${SESSION.id}`, {
      pinned: true,
    });
    expect(useChatStore.getState().sessions.map((item) => item.id)).toEqual([
      SESSION.id,
      other.id,
    ]);
  });

  it('показывает ошибку, если не удалось обновить сессию (S43-001)', async () => {
    vi.spyOn(api, 'patch').mockRejectedValue(new Error('boom'));
    useChatStore.setState({ sessions: [SESSION] });

    await useChatStore.getState().renameSession(SESSION.id, 'Новое имя');

    expect(useChatStore.getState().error).toBe('Не удалось обновить чат');
  });

  it('удаляет сессию из списка и сбрасывает активную', async () => {
    useChatStore.setState({ sessions: [SESSION], active: SESSION_WITH_MESSAGES });
    vi.spyOn(api, 'delete').mockResolvedValue(undefined);

    await useChatStore.getState().deleteSession(SESSION.id);

    expect(useChatStore.getState().sessions).toHaveLength(0);
    expect(useChatStore.getState().active).toBeNull();
  });

  it('загружает контекст задачи для deep-link', async () => {
    vi.spyOn(api, 'get').mockResolvedValue({
      id: TASK_ID,
      title: 'Сумма двух чисел',
      description: 'Считайте два числа.',
      difficulty: 'easy',
      category: 'input_output',
      hints: [],
      solution_template: null,
      test_cases_count: 2,
      status: 'not_started',
      attempts: 0,
    });

    await useChatStore.getState().loadTaskContext(TASK_ID);

    expect(useChatStore.getState().taskContext).toEqual({
      id: TASK_ID,
      title: 'Сумма двух чисел',
    });
  });

  it('очищает контекст задачи', () => {
    useChatStore.setState({ taskContext: { id: TASK_ID, title: 'Задача' } });

    useChatStore.getState().clearTaskContext();

    expect(useChatStore.getState().taskContext).toBeNull();
  });

  it('REST-фолбэк передаёт task_id, не подмешивая его в текст', async () => {
    useChatStore.setState({ active: { ...SESSION_WITH_MESSAGES, messages: [] } });
    const post = vi.spyOn(api, 'post').mockResolvedValue({
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

    await useChatStore.getState().sendViaRest('вопрос', TASK_ID);

    expect(post).toHaveBeenCalledWith(`/chat/sessions/${SESSION.id}/messages`, {
      content: 'вопрос',
      task_id: TASK_ID,
    });
  });
});
