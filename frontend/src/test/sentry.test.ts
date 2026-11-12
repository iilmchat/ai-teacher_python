import { afterEach, describe, expect, it, vi } from 'vitest';

import * as Sentry from '@sentry/react';
import { initSentry, scrubSentryEvent } from '@/lib/sentry';

vi.mock('@sentry/react', () => ({
  init: vi.fn(),
  browserTracingIntegration: vi.fn(() => ({ name: 'BrowserTracing' })),
}));

afterEach(() => {
  vi.clearAllMocks();
  delete window.__APP_CONFIG__;
});

describe('sentry frontend', () => {
  it('без DSN не инициализируется (no-op)', () => {
    expect(initSentry()).toBe(false);
    expect(Sentry.init).not.toHaveBeenCalled();
  });

  it('инициализируется из runtime-конфига без PII', () => {
    window.__APP_CONFIG__ = {
      sentryDsn: 'https://key@o1.ingest.sentry.io/2',
      sentryEnvironment: 'production',
      release: '0.6.0+abc',
      sentryTracesSampleRate: 0.1,
    };

    expect(initSentry()).toBe(true);

    const options = (Sentry.init as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(options.dsn).toContain('ingest.sentry.io');
    expect(options.dataCollection.userInfo).toBe(false);
    expect(options.dataCollection.cookies).toBe(false);
    expect(options.dataCollection.httpHeaders).toBe(false);
    expect(options.dataCollection.httpBodies).toEqual([]);
    expect(options.dataCollection.urlQueryParams).toBe(false);
    expect(options.tracesSampleRate).toBe(0.1);
    expect(typeof options.beforeSend).toBe('function');
  });

  it('beforeSend удаляет тело запроса, cookies и query', () => {
    const event = scrubSentryEvent({
      request: {
        data: { code: 'print(1)' },
        cookies: { session: 'abc' },
        query_string: 'refresh_token=leak',
        headers: { Authorization: 'Bearer x', 'X-Forwarded-For': '203.0.113.5' },
      },
    });

    const request = event.request as Record<string, unknown>;
    expect(request.data).toBeUndefined();
    expect(request.cookies).toBeUndefined();
    expect(request.query_string).toBeUndefined();
    const headers = request.headers as Record<string, string>;
    expect(headers.Authorization).toBe('<filtered>');
    expect(headers['X-Forwarded-For']).toBe('<filtered>');
  });

  it('beforeSend оставляет только id пользователя', () => {
    const event = scrubSentryEvent({
      user: { id: 'u-1', email: 'student@example.com', ip_address: '203.0.113.5' },
    });

    expect(event.user).toEqual({ id: 'u-1' });
  });

  it('beforeSend фильтрует код, промпты и маскирует email/IP', () => {
    const event = scrubSentryEvent({
      extra: {
        user_code: 'def solve(): pass',
        llm_prompt: 'Объясни решение',
        provider: 'deepseek',
        note: 'student@example.com from 203.0.113.5',
      },
    });

    const extra = event.extra as Record<string, string>;
    expect(extra.user_code).toBe('<filtered>');
    expect(extra.llm_prompt).toBe('<filtered>');
    expect(extra.provider).toBe('deepseek');
    expect(extra.note).toBe('<email> from <ip>');
  });
});
