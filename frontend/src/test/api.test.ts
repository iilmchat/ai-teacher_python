import { describe, expect, it, vi } from 'vitest';

import { ApiError, api, UNAUTHORIZED_EVENT } from '@/lib/api';
import { getAccessToken, setTokens } from '@/lib/token';
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

describe('api client', () => {
  it('возвращает данные успешного ответа', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(USER)));

    const result = await api.get<typeof USER>('/auth/me');

    expect(result.username).toBe('tester');
  });

  it('превращает ошибку API в ApiError с сообщением из detail', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'Неверный пароль' }, 400)),
    );

    await expect(api.anonymousPost('/auth/login')).rejects.toMatchObject({
      name: 'ApiError',
      status: 400,
      message: 'Неверный пароль',
    });
  });

  it('склеивает ошибки валидации Pydantic', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          { detail: [{ msg: 'Поле обязательно' }, { msg: 'Слишком короткий пароль' }] },
          422,
        ),
      ),
    );

    await expect(api.anonymousPost('/auth/register')).rejects.toThrow(
      'Поле обязательно; Слишком короткий пароль',
    );
  });

  it('подставляет Authorization из localStorage', async () => {
    setTokens({ access: 'access-token', refresh: 'refresh-token' });
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(USER));
    vi.stubGlobal('fetch', fetchMock);

    await api.get('/auth/me');

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe(
      'Bearer access-token',
    );
  });

  it('обновляет access-токен по refresh и повторяет запрос', async () => {
    setTokens({ access: 'expired', refresh: 'valid-refresh' });

    const fetchMock = vi
      .fn()
      // первый запрос — 401
      .mockResolvedValueOnce(jsonResponse({ detail: 'Token expired' }, 401))
      // refresh — новая пара
      .mockResolvedValueOnce(
        jsonResponse({ access_token: 'fresh', refresh_token: 'new-refresh' }),
      )
      // повторный запрос — успех
      .mockResolvedValueOnce(jsonResponse(USER));
    vi.stubGlobal('fetch', fetchMock);

    const result = await api.get<typeof USER>('/auth/me');

    expect(result.username).toBe('tester');
    expect(getAccessToken()).toBe('fresh');
    expect(fetchMock).toHaveBeenCalledTimes(3);

    // S34-002: refresh-токен уходит в теле JSON, а не в query string.
    const refreshCall = fetchMock.mock.calls[1];
    expect(refreshCall[0]).toBe('/api/v1/auth/refresh');
    const refreshInit = refreshCall[1] as RequestInit;
    expect(refreshInit.method).toBe('POST');
    expect(JSON.parse(refreshInit.body as string)).toEqual({
      refresh_token: 'valid-refresh',
    });
  });

  it('разлогинивает, если refresh невозможен', async () => {
    setTokens({ access: 'expired', refresh: 'bad-refresh' });
    const listener = vi.fn();
    window.addEventListener(UNAUTHORIZED_EVENT, listener);

    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse({ detail: 'expired' }, 401))
        .mockResolvedValueOnce(jsonResponse({ detail: 'invalid' }, 401)),
    );

    await expect(api.get('/auth/me')).rejects.toBeInstanceOf(ApiError);

    expect(listener).toHaveBeenCalledTimes(1);
    expect(getAccessToken()).toBeNull();
    window.removeEventListener(UNAUTHORIZED_EVENT, listener);
  });
});
