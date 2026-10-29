import { beforeEach, describe, expect, it, vi } from 'vitest';

import { api } from '@/lib/api';
import { getAccessToken, getRefreshToken } from '@/lib/token';
import { useAuthStore } from '@/store/auth';
import { jsonResponse } from '@/test/utils';

const USER = {
  id: '11111111-1111-1111-1111-111111111111',
  email: 'test@example.com',
  username: 'tester',
  role: 'student' as const,
  level: 'basic' as const,
  created_at: '2026-10-29T10:00:00',
  last_active: '2026-10-29T10:00:00',
  settings: {},
};

function resetStore(): void {
  useAuthStore.setState({
    user: null,
    initializing: false,
    loading: false,
    error: null,
  });
}

describe('auth store', () => {
  beforeEach(() => {
    resetStore();
  });

  it('логин сохраняет токены и профиль', async () => {
    vi.spyOn(api, 'anonymousPostForm').mockResolvedValue({
      access_token: 'access',
      refresh_token: 'refresh',
      token_type: 'bearer',
      user: USER,
    });
    vi.spyOn(api, 'get').mockResolvedValue(USER);

    await useAuthStore.getState().login('tester', 'password123');

    const state = useAuthStore.getState();
    expect(state.user?.username).toBe('tester');
    expect(state.error).toBeNull();
    expect(getAccessToken()).toBe('access');
    expect(getRefreshToken()).toBe('refresh');
  });

  it('ошибка логина сохраняется в error', async () => {
    vi.spyOn(api, 'anonymousPostForm').mockRejectedValue(new Error('boom'));

    await expect(
      useAuthStore.getState().login('tester', 'wrong'),
    ).rejects.toThrow('boom');

    expect(useAuthStore.getState().error).toBeTruthy();
    expect(useAuthStore.getState().user).toBeNull();
  });

  it('регистрация сразу выполняет вход', async () => {
    const registerSpy = vi.spyOn(api, 'anonymousPost').mockResolvedValue(USER);
    vi.spyOn(api, 'anonymousPostForm').mockResolvedValue({
      access_token: 'access',
      refresh_token: 'refresh',
      token_type: 'bearer',
      user: USER,
    });
    vi.spyOn(api, 'get').mockResolvedValue(USER);

    await useAuthStore.getState().register('test@example.com', 'tester', 'password123');

    expect(registerSpy).toHaveBeenCalledWith('/auth/register', {
      email: 'test@example.com',
      username: 'tester',
      password: 'password123',
    });
    expect(useAuthStore.getState().user?.username).toBe('tester');
  });

  it('logout очищает токены и профиль', () => {
    localStorage.setItem('ai-teacher.access', 'a');
    localStorage.setItem('ai-teacher.refresh', 'r');
    useAuthStore.setState({ user: USER });

    useAuthStore.getState().logout();

    expect(useAuthStore.getState().user).toBeNull();
    expect(getAccessToken()).toBeNull();
  });

  it('смена уровня обновляет профиль', async () => {
    useAuthStore.setState({ user: USER });
    vi.spyOn(api, 'patch').mockResolvedValue({ ...USER, level: 'advanced' });

    await useAuthStore.getState().setLevel('advanced');

    expect(useAuthStore.getState().user?.level).toBe('advanced');
  });

  it('loadMe без токена завершает инициализацию без запроса', async () => {
    const getSpy = vi.spyOn(api, 'get');
    useAuthStore.setState({ initializing: true });

    await useAuthStore.getState().loadMe();

    expect(getSpy).not.toHaveBeenCalled();
    expect(useAuthStore.getState().initializing).toBe(false);
  });

  it('loadMe с токеном загружает профиль', async () => {
    localStorage.setItem('ai-teacher.access', 'token');
    localStorage.setItem('ai-teacher.refresh', 'refresh');
    vi.spyOn(api, 'get').mockResolvedValue(USER);
    useAuthStore.setState({ initializing: true });

    await useAuthStore.getState().loadMe();

    expect(useAuthStore.getState().user?.email).toBe('test@example.com');
    expect(useAuthStore.getState().initializing).toBe(false);
  });

  it('loadMe при ошибке очищает токены', async () => {
    localStorage.setItem('ai-teacher.access', 'token');
    localStorage.setItem('ai-teacher.refresh', 'refresh');
    vi.spyOn(api, 'get').mockRejectedValue(new Error('401'));

    await useAuthStore.getState().loadMe();

    expect(getAccessToken()).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
  });
});

describe('login response fixture', () => {
  it('jsonResponse собирает валидный ответ', async () => {
    const response = jsonResponse({ ok: true });
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ ok: true });
  });
});
