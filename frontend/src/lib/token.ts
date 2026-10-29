/**
 * Хранилище токенов в localStorage.
 *
 * Вынесено отдельно от Zustand-стора, чтобы API-клиент мог читать токены
 * без циклического импорта `api ↔ store`.
 */

const ACCESS_KEY = 'ai-teacher.access';
const REFRESH_KEY = 'ai-teacher.refresh';

export interface TokenPair {
  access: string;
  refresh: string;
}

export function getTokens(): TokenPair | null {
  const access = localStorage.getItem(ACCESS_KEY);
  const refresh = localStorage.getItem(REFRESH_KEY);
  if (!access || !refresh) {
    return null;
  }
  return { access, refresh };
}

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(tokens: TokenPair): void {
  localStorage.setItem(ACCESS_KEY, tokens.access);
  localStorage.setItem(REFRESH_KEY, tokens.refresh);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}
