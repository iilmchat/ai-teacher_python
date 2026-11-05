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

  loadSessions: () => Promise<void>;
  createSession: (level?: UserLevel) => Promise<ChatSession>;
  openSession: (sessionId: string) => Promise<void>;
  closeSession: () => void;
  deleteSession: (sessionId: string) => Promise<void>;
  loadTaskContext: (taskId: string) => Promise<void>;
  clearTaskContext: () => void;

  /** Добавить вопрос ученика локально (оптимистично) */
  addUserMessage: (content: string) => void;
  startAssistantDraft: () => void;
  appendToken: (delta: string) => void;
  finishStream: (full?: string, warnings?: string[]) => void;
  failStream: (message: string) => void;
  /** Отправка без стриминга (fallback); taskId — контекст задачи */
  sendViaRest: (content: string, taskId?: string | null) => Promise<void>;
}

function nowIso(): string {
  return new Date().toISOString();
}

function localMessage(
  sessionId: string,
  role: ChatMessage['role'],
  content: string,
  warnings: string[] = [],
): ChatMessage {
  return {
    id: `local-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    session_id: sessionId,
    role,
    content,
    code_blocks: [],
    created_at: nowIso(),
    metadata: {},
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
    set((state) => ({ sessions: [session, ...state.sessions] }));
    return session;
  },

  async openSession(sessionId) {
    set({ loading: true, error: null, draft: '' });
    try {
      const active = await api.get<ChatSessionWithMessages>(
        `/chat/sessions/${sessionId}`,
      );
      set({ active, loading: false, streaming: false });
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

  addUserMessage(content) {
    const active = get().active;
    if (!active) {
      return;
    }
    set({
      active: {
        ...active,
        messages: [...active.messages, localMessage(active.id, 'user', content)],
      },
    });
  },

  startAssistantDraft() {
    set({ draft: '', streaming: true });
  },

  appendToken(delta) {
    set((state) => ({ draft: state.draft + delta }));
  },

  finishStream(full, warnings = []) {
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
          localMessage(active.id, 'assistant', content, warnings),
        ],
      },
      draft: '',
      streaming: false,
    });
  },

  failStream(message) {
    set({ streaming: false, draft: '', error: message });
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
