/**
 * Состояние чата (Zustand): сессии, сообщения, стриминг.
 *
 * Сообщения ассистента собираются из токенов WebSocket; если сокет
 * недоступен, используется REST-эндпоинт (без стриминга).
 */

import i18n from '@/i18n';
import { create } from 'zustand';

import { api } from '@/lib/api';
import type {
  ChatMessage,
  ChatSession,
  ChatSessionWithMessages,
  ChatTurn,
  MessageFeedback,
  TaskDetail,
  UserLevel,
} from '@/types/api';

/** Задача, условие которой передаётся ассистенту (S42-006) */
export interface ChatTaskContext {
  id: string;
  title: string;
}

interface ChatState {
  sessions: ChatSession[];
  active: ChatSessionWithMessages | null;
  /** Черновик ответа ассистента во время стриминга */
  draft: string;
  streaming: boolean;
  loading: boolean;
  error: string | null;
  /** Контекст задачи из deep-link `/chat?task=<id>` (S42-006) */
  taskContext: ChatTaskContext | null;
  /** Мои оценки ответов ассистента: id сообщения → оценка (S43-003) */
  feedback: Record<string, MessageFeedback>;

  loadSessions: () => Promise<void>;
  createSession: (level?: UserLevel) => Promise<ChatSession>;
  openSession: (sessionId: string) => Promise<void>;
  closeSession: () => void;
  deleteSession: (sessionId: string) => Promise<void>;
  renameSession: (sessionId: string, title: string) => Promise<void>;
  togglePin: (sessionId: string, pinned: boolean) => Promise<void>;
  loadTaskContext: (taskId: string) => Promise<void>;
  clearTaskContext: () => void;
  /** Мои оценки ответов сессии (S43-003) */
  loadFeedback: (sessionId: string) => Promise<void>;
  /** Оценить ответ ассистента (S43-003) */
  setFeedback: (messageId: string, value: 1 | -1, comment?: string | null) => Promise<void>;
  /** Снять свою оценку ответа (S43-003) */
  clearFeedback: (messageId: string) => Promise<void>;

  /** Добавить вопрос ученика локально (оптимистично) */
  addUserMessage: (content: string) => void;
  startAssistantDraft: () => void;
  appendToken: (delta: string) => void;
  finishStream: (
    full?: string,
    warnings?: string[],
    stopped?: boolean,
    messageId?: string,
  ) => void;
  failStream: (message: string) => void;
  /** Перегенерировать ответ ассистента (S43-002) */
  regenerate: (messageId: string) => Promise<void>;
  /** Отправка без стриминга (fallback); taskId — контекст задачи */
  sendViaRest: (content: string, taskId?: string | null) => Promise<void>;
}

function nowIso(): string {
  return new Date().toISOString();
}

/** Авто-заголовок из первого вопроса: одна строка, до 60 символов (S43-001) */
function autoTitle(content: string): string {
  return content.trim().split(/\s+/).join(' ').slice(0, 60).trim();
}

/** Порядок списка: закреплённые сверху, затем по времени обновления */
function sortSessions(sessions: ChatSession[]): ChatSession[] {
  return [...sessions].sort((a, b) => {
    if (a.pinned !== b.pinned) {
      return a.pinned ? -1 : 1;
    }
    return b.updated_at.localeCompare(a.updated_at);
  });
}

function localMessage(
  sessionId: string,
  role: ChatMessage['role'],
  content: string,
  warnings: string[] = [],
  metadata: Record<string, unknown> = {},
  messageId?: string,
): ChatMessage {
  return {
    id: messageId ?? `local-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    session_id: sessionId,
    role,
    content,
    code_blocks: [],
    created_at: nowIso(),
    metadata,
    warnings,
  };
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessions: [],
  active: null,
  draft: '',
  streaming: false,
  loading: false,
  error: null,
  taskContext: null,
  feedback: {},

  async loadSessions() {
    set({ loading: true, error: null });
    try {
      const sessions = await api.get<ChatSession[]>('/chat/sessions');
      set({ sessions, loading: false });
    } catch {
      set({ loading: false, error: i18n.t('errors.chatList') });
    }
  },

  async createSession(level) {
    const session = await api.post<ChatSession>(
      '/chat/sessions',
      level ? { level } : {},
    );
    set((state) => ({ sessions: sortSessions([session, ...state.sessions]) }));
    return session;
  },

  async openSession(sessionId) {
    set({ loading: true, error: null, draft: '' });
    try {
      const active = await api.get<ChatSessionWithMessages>(
        `/chat/sessions/${sessionId}`,
      );
      set({ active, loading: false, streaming: false });
      // Оценки ответов показываем сразу при открытии чата (S43-003)
      void get().loadFeedback(sessionId);
    } catch {
      set({ loading: false, error: i18n.t('errors.chatOpen') });
    }
  },
  closeSession() {
    set({ active: null, draft: '', streaming: false });
  },

  async deleteSession(sessionId) {
    await api.delete(`/chat/sessions/${sessionId}`);
    set((state) => ({
      sessions: state.sessions.filter((item) => item.id !== sessionId),
      active: state.active?.id === sessionId ? null : state.active,
    }));
  },

  async renameSession(sessionId, title) {
    try {
      const updated = await api.patch<ChatSession>(
        `/chat/sessions/${sessionId}`,
        { title },
      );
      set((state) => ({
        sessions: sortSessions(
          state.sessions.map((item) =>
            item.id === sessionId ? { ...item, ...updated } : item,
          ),
        ),
        active:
          state.active?.id === sessionId
            ? { ...state.active, ...updated }
            : state.active,
      }));
    } catch {
      set({ error: i18n.t('errors.chatUpdate') });
    }
  },

  async togglePin(sessionId, pinned) {
    try {
      const updated = await api.patch<ChatSession>(
        `/chat/sessions/${sessionId}`,
        { pinned },
      );
      set((state) => ({
        sessions: sortSessions(
          state.sessions.map((item) =>
            item.id === sessionId ? { ...item, ...updated } : item,
          ),
        ),
        active:
          state.active?.id === sessionId
            ? { ...state.active, ...updated }
            : state.active,
      }));
    } catch {
      set({ error: i18n.t('errors.chatUpdate') });
    }
  },

  async loadTaskContext(taskId) {
    try {
      const task = await api.get<TaskDetail>(`/tasks/${taskId}`);
      set({ taskContext: { id: task.id, title: task.title } });
    } catch {
      // Задача удалена или недоступна — контекст не подставляем.
      set({ taskContext: null });
    }
  },

  clearTaskContext() {
    set({ taskContext: null });
  },

  async loadFeedback(sessionId) {
    try {
      const items = await api.get<MessageFeedback[]>(
        `/chat/sessions/${sessionId}/feedback`,
      );
      set({
        feedback: Object.fromEntries(
          items.map((item) => [item.message_id, item]),
        ),
      });
    } catch {
      // Оценки не загрузились — чат остаётся рабочим, просто без меток.
      set({ feedback: {} });
    }
  },

  async setFeedback(messageId, value, comment) {
    try {
      const item = await api.post<MessageFeedback>(
        `/chat/messages/${messageId}/feedback`,
        { value, comment: comment ?? null },
      );
      set((state) => ({
        feedback: { ...state.feedback, [messageId]: item },
        error: null,
      }));
    } catch {
      set({ error: i18n.t('errors.chatFeedback') });
    }
  },

  async clearFeedback(messageId) {
    try {
      await api.delete(`/chat/messages/${messageId}/feedback`);
      set((state) => {
        const feedback = { ...state.feedback };
        delete feedback[messageId];
        return { feedback };
      });
    } catch {
      set({ error: i18n.t('errors.chatFeedback') });
    }
  },

  addUserMessage(content) {
    const active = get().active;
    if (!active) {
      return;
    }
    // Первое сообщение задаёт заголовок и в списке сессий (S43-001),
    // чтобы не делать лишний запрос: логика совпадает с backend.
    const title = active.title ?? autoTitle(content);
    const updatedAt = nowIso();
    set((state) => ({
      active: {
        ...active,
        title,
        updated_at: updatedAt,
        messages: [...active.messages, localMessage(active.id, 'user', content)],
      },
      sessions: sortSessions(
        state.sessions.map((item) =>
          item.id === active.id
            ? { ...item, title, updated_at: updatedAt }
            : item,
        ),
      ),
    }));
  },

  startAssistantDraft() {
    set({ draft: '', streaming: true });
  },

  appendToken(delta) {
    set((state) => ({ draft: state.draft + delta }));
  },

  finishStream(full, warnings = [], stopped = false, messageId) {
    const { active, draft } = get();
    const content = (full ?? draft).trim();
    if (!active || !content) {
      set({ streaming: false, draft: '' });
      return;
    }
    set({
      active: {
        ...active,
        messages: [
          ...active.messages,
          localMessage(
            active.id,
            'assistant',
            content,
            warnings,
            stopped ? { stopped: true } : {},
            // Настоящий id сообщения нужен для оценки ответа (S43-003).
            messageId,
          ),
        ],
      },
      draft: '',
      streaming: false,
    });
  },

  failStream(message) {
    set({ streaming: false, draft: '', error: message });
  },

  async regenerate(messageId) {
    const active = get().active;
    if (!active) {
      return;
    }
    set({ loading: true, error: null });
    try {
      const updated = await api.post<ChatMessage>(
        `/chat/sessions/${active.id}/messages/${messageId}/regenerate`,
      );
      set((state) => ({
        active: state.active
          ? {
              ...state.active,
              // Новый ответ занимает место старого — диалог не разрастается.
              messages: state.active.messages.map((message) =>
                message.id === messageId ? updated : message,
              ),
            }
          : null,
        loading: false,
      }));
    } catch {
      set({ loading: false, error: i18n.t('errors.chatRegenerate') });
    }
  },

  async sendViaRest(content, taskId) {
    const active = get().active;
    if (!active) {
      return;
    }
    set({ loading: true, error: null });
    try {
      const turn = await api.post<ChatTurn>(
        `/chat/sessions/${active.id}/messages`,
        taskId ? { content, task_id: taskId } : { content },
      );
      const current = get().active;
      if (!current) {
        return;
      }
      set({
        active: {
          ...current,
          messages: [...current.messages, turn.assistant_message],
        },
        loading: false,
      });
    } catch {
      set({ loading: false, error: i18n.t('errors.chatSend') });
    }
  },
}));
