/**
 * Sentry для frontend (S35-002).
 *
 * DSN берётся из runtime-конфига `window.__APP_CONFIG__` (файл `/config.js`,
 * генерируется контейнером при старте) или из `VITE_SENTRY_DSN` на этапе
 * сборки. Без DSN модуль — no-op.
 *
 * PII: `sendDefaultPii: false`, тела запросов не отправляются, `beforeSend`
 * вычищает email, IP, токены, тексты кода и промптов.
 */
import * as Sentry from '@sentry/react';

export interface AppRuntimeConfig {
  sentryDsn?: string;
  sentryEnvironment?: string;
  release?: string;
  sentryTracesSampleRate?: number;
}

declare global {
  interface Window {
    __APP_CONFIG__?: AppRuntimeConfig;
  }
}

type EventLike = Record<string, unknown>;

const SENSITIVE_KEYS = new Set([
  'code',
  'source',
  'prompt',
  'prompts',
  'messages',
  'completion',
  'content',
  'email',
  'username',
  'ip',
  'ip_address',
  'password',
  'secret',
  'token',
  'access_token',
  'refresh_token',
  'authorization',
  'cookie',
  'cookies',
  'api_key',
  'dsn',
  'query',
  'query_string',
  'body',
  'data',
]);

const SENSITIVE_FRAGMENTS = [
  'prompt',
  'code',
  'email',
  'password',
  'secret',
  'token',
  'api_key',
  'authorization',
  'cookie',
  'dsn',
  'forwarded',
];

const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
const IPV4_RE = /\b(?:\d{1,3}\.){3}\d{1,3}\b/g;

function isSensitiveKey(key: string): boolean {
  const lowered = key.toLowerCase();
  return (
    SENSITIVE_KEYS.has(lowered) ||
    SENSITIVE_FRAGMENTS.some((fragment) => lowered.includes(fragment))
  );
}

function maskText(value: string): string {
  return value.replace(EMAIL_RE, '<email>').replace(IPV4_RE, '<ip>');
}

function scrub(value: unknown, key?: string): unknown {
  if (key !== undefined && isSensitiveKey(key)) {
    return '<filtered>';
  }
  if (Array.isArray(value)) {
    return value.map((item) => scrub(item, key));
  }
  if (value && typeof value === 'object') {
    const result: EventLike = {};
    for (const [childKey, childValue] of Object.entries(value)) {
      result[childKey] = scrub(childValue, childKey);
    }
    return result;
  }
  if (typeof value === 'string') {
    return maskText(value);
  }
  return value;
}

/** Очистить событие Sentry от PII перед отправкой. */
export function scrubSentryEvent(event: EventLike): EventLike {
  try {
    const result = { ...event };

    const request = result.request;
    if (request && typeof request === 'object') {
      const req = { ...(request as EventLike) };
      delete req.data;
      delete req.cookies;
      delete req.query_string;
      result.request = scrub(req) as EventLike;
    }

    if (result.user && typeof result.user === 'object') {
      const user = result.user as EventLike;
      result.user = Object.fromEntries(
        Object.entries(user).filter(([key]) => key === 'id' || key === 'segment'),
      );
    }

    for (const field of ['extra', 'contexts', 'tags', 'breadcrumbs', 'exception']) {
      if (field in result) {
        result[field] = scrub(result[field]);
      }
    }

    if (typeof result.message === 'string') {
      result.message = maskText(result.message);
    }

    return result;
  } catch {
    // Фильтр не должен мешать отправке события.
    return event;
  }
}

/** Инициализировать Sentry. Возвращает false, если DSN не задан. */
export function initSentry(): boolean {
  const runtime = window.__APP_CONFIG__ ?? {};
  const dsn = runtime.sentryDsn || import.meta.env.VITE_SENTRY_DSN || '';
  if (!dsn) {
    return false;
  }

  const tracesSampleRate = Number(
    runtime.sentryTracesSampleRate ?? import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE ?? 0,
  );

  Sentry.init({
    dsn,
    environment: runtime.sentryEnvironment || import.meta.env.MODE || 'production',
    release: runtime.release || import.meta.env.VITE_APP_RELEASE || undefined,
    integrations: [Sentry.browserTracingIntegration()],
    tracesSampleRate: Number.isFinite(tracesSampleRate) ? tracesSampleRate : 0,
    // S35-002: не собираем пользователя, cookies, заголовки, тела и query.
    dataCollection: {
      userInfo: false,
      cookies: false,
      httpHeaders: false,
      httpBodies: [],
      urlQueryParams: false,
    },
    beforeSend: (event) =>
      scrubSentryEvent(event as unknown as EventLike) as unknown as typeof event,
  });

  return true;
}
