/**
 * HTTP-клиент API (RULES §3.2): единая точка для запросов, типизированные
 * ответы, автоматическая подстановка токена и обновление по refresh-токену.
 */

import { clearTokens, getAccessToken, getRefreshToken, setTokens } from '@/lib/token';

const API_BASE: string = import.meta.env.VITE_API_BASE ?? '/api/v1';

/** Ошибка API с человекочитаемым сообщением */
export class ApiError extends Error {
  readonly status: number;
  readonly details: unknown;

  constructor(status: number, message: string, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  body?: unknown;
  form?: Record<string, string>;
  /** Файл для multipart-загрузки */
  file?: File;
  /** Не добавлять Authorization (для login/register) */
  anonymous?: boolean;
}

/** Событие «сессия истекла» — стор подписывается и разлогинивает пользователя */
export const UNAUTHORIZED_EVENT = 'auth:unauthorized';

function extractDetail(payload: unknown): string {
  if (typeof payload === 'string') {
    return payload;
  }
  if (payload && typeof payload === 'object' && 'detail' in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === 'string') {
      return detail;
    }
    if (Array.isArray(detail)) {
      // Ошибки валидации Pydantic: [{loc, msg, type}]
      const messages = detail
        .map((item) =>
          item && typeof item === 'object' && 'msg' in item
            ? String((item as { msg: unknown }).msg)
            : String(item),
        )
        .filter(Boolean);
      if (messages.length > 0) {
        return messages.join('; ');
      }
    }
  }
  return 'Не удалось выполнить запрос';
}

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    return null;
  }

  try {
    const response = await fetch(
      `${API_BASE}/auth/refresh?refresh_token=${encodeURIComponent(refreshToken)}`,
      { method: 'POST' },
    );
    if (!response.ok) {
      return null;
    }
    const data = (await response.json()) as {
      access_token: string;
      refresh_token: string;
    };
    setTokens({ access: data.access_token, refresh: data.refresh_token });
    return data.access_token;
  } catch {
    return null;
  }
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;

  if (options.form) {
    headers['Content-Type'] = 'application/x-www-form-urlencoded';
    body = new URLSearchParams(options.form).toString();
  } else if (options.file) {
    const formData = new FormData();
    formData.append('file', options.file);
    body = formData;
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(options.body);
  }

  if (!options.anonymous) {
    const token = getAccessToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }

  return fetch(`${API_BASE}${path}`, {
    method: options.method ?? 'GET',
    headers,
    body,
  });
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await send(path, options);

  // Access-токен истёк: обновляем один раз и повторяем запрос
  if (response.status === 401 && !options.anonymous) {
    const newToken = await refreshAccessToken();
    if (!newToken) {
      clearTokens();
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
      throw new ApiError(401, 'Сессия истекла, войдите заново');
    }
    response = await send(path, options);
  }

  const payload = await parseBody(response);

  if (!response.ok) {
    throw new ApiError(response.status, extractDetail(payload), payload);
  }

  return payload as T;
}

export const api = {
  get: <T>(path: string) => apiRequest<T>(path),
  post: <T>(path: string, body?: unknown) =>
    apiRequest<T>(path, { method: 'POST', body }),
  postForm: <T>(path: string, form: Record<string, string>) =>
    apiRequest<T>(path, { method: 'POST', form }),
  postFile: <T>(path: string, file: File) =>
    apiRequest<T>(path, { method: 'POST', file }),
  patch: <T>(path: string, body?: unknown) =>
    apiRequest<T>(path, { method: 'PATCH', body }),
  delete: <T>(path: string) => apiRequest<T>(path, { method: 'DELETE' }),
  anonymousPostForm: <T>(path: string, form: Record<string, string>) =>
    apiRequest<T>(path, { method: 'POST', form, anonymous: true }),
  anonymousPost: <T>(path: string, body?: unknown) =>
    apiRequest<T>(path, { method: 'POST', body, anonymous: true }),
};
