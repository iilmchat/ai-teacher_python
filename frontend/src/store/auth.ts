/**
 * Состояние аутентификации (Zustand).
 *
 * Токены живут в `lib/token.ts` (localStorage), стор хранит профиль и статус.
 */

import i18n from '@/i18n';
import { create } from 'zustand';

import { api, ApiError, UNAUTHORIZED_EVENT } from '@/lib/api';
import { clearTokens, getAccessToken, setTokens } from '@/lib/token';
import type {
  CodeSnippet,
  LoginResponse,
  PasswordChangeResponse,
  User,
  UserLevel,
} from '@/types/api';

interface AuthState {
  user: User | null;
  /** Флаг первичной проверки сессии */
  initializing: boolean;
  loading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => void;
  loadMe: () => Promise<void>;
  setLevel: (level: UserLevel) => Promise<void>;
  /** Правка e-mail/имени через PATCH /auth/me (S45-002) */
  updateProfile: (data: { email?: string; username?: string }) => Promise<void>;
  /** Удалить аккаунт навсегда (S45-002): очищает локальную сессию */
  deleteAccount: (password: string) => Promise<void>;
  /** Сменить пароль: отзыв старых refresh-токенов, текущая сессия жива (S45-001) */
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  /** Сохранить выбранный шаблон промпта в личных настройках (S43-004) */
  setPromptTemplate: (templateId: string | null) => Promise<void>;
  /** Заменить список личных сниппетов кода (S44-003) */
  setCodeSnippets: (snippets: CodeSnippet[]) => Promise<void>;
  clearError: () => void;
}

const USER_KEY = 'ai-teacher.user';

function readCachedUser(): User | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

function cacheUser(user: User | null): void {
  if (user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } else {
    localStorage.removeItem(USER_KEY);
  }
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: readCachedUser(),
  initializing: Boolean(getAccessToken()),
  loading: false,
  error: null,

  async login(username, password) {
    set({ loading: true, error: null });
    try {
      const data = await api.anonymousPostForm<LoginResponse>('/auth/login', {
        username,
        password,
      });
      setTokens({ access: data.access_token, refresh: data.refresh_token });
      const user = await api.get<User>('/auth/me');
      cacheUser(user);
      set({ user, loading: false, initializing: false });
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : i18n.t('errors.login');
      set({ loading: false, error: message });
      throw error;
    }
  },

  async register(email, username, password) {
    set({ loading: true, error: null });
    try {
      await api.anonymousPost<User>('/auth/register', { email, username, password });
      await get().login(username, password);
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : i18n.t('errors.register');
      set({ loading: false, error: message });
      throw error;
    }
  },

  logout() {
    clearTokens();
    cacheUser(null);
    set({ user: null, error: null, initializing: false });
  },

  async loadMe() {
    if (!getAccessToken()) {
      set({ user: null, initializing: false });
      return;
    }
    try {
      const user = await api.get<User>('/auth/me');
      cacheUser(user);
      set({ user, initializing: false });
    } catch {
      clearTokens();
      cacheUser(null);
      set({ user: null, initializing: false });
    }
  },

  async setLevel(level) {
    const user = await api.patch<User>('/users/me/level', { level });
    cacheUser(user);
    set({ user });
  },

  async changePassword(currentPassword, newPassword) {
    // Сервер отзывает все выданные раньше refresh-токены и возвращает
    // новую пару для текущего устройства (S45-001, KI-028).
    const tokens = await api.post<PasswordChangeResponse>('/users/me/password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    setTokens({ access: tokens.access_token, refresh: tokens.refresh_token });
    await get().loadMe();
  },

  async updateProfile(data) {
    const user = await api.patch<User>('/auth/me', data);
    cacheUser(user);
    set({ user });
  },

  async deleteAccount(password) {
    // Сервер анонимизирует аккаунт и блокирует вход (S26-004).
    // Локальную сессию убираем только после успешного удаления: если
    // пароль неверен, аккаунт остаётся живым и разлогин был бы ложным.
    await api.delete<unknown>('/auth/me', { password });
    get().logout();
  },

  async setPromptTemplate(templateId) {
    const user = await api.patch<User>('/users/me/settings', {
      prompt_template: templateId,
    });
    cacheUser(user);
    set({ user });
  },

  async setCodeSnippets(snippets) {
    const user = await api.patch<User>('/users/me/settings', { snippets });
    cacheUser(user);
    set({ user });
  },

  clearError() {
    set({ error: null });
  },
}));

// Сессия истекла на уровне API-клиента — разлогиниваем
window.addEventListener(UNAUTHORIZED_EVENT, () => {
  useAuthStore.getState().logout();
});
