/**
 * Состояние аутентификации (Zustand).
 *
 * Токены живут в `lib/token.ts` (localStorage), стор хранит профиль и статус.
 */

import i18n from '@/i18n';
import { create } from 'zustand';

import { api, ApiError, UNAUTHORIZED_EVENT } from '@/lib/api';
import { clearTokens, getAccessToken, setTokens } from '@/lib/token';
import type { LoginResponse, User, UserLevel } from '@/types/api';

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

  clearError() {
    set({ error: null });
  },
}));

// Сессия истекла на уровне API-клиента — разлогиниваем
window.addEventListener(UNAUTHORIZED_EVENT, () => {
  useAuthStore.getState().logout();
});
