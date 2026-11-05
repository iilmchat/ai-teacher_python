import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { openChatSocket } from '@/lib/chatSocket';

const TASK_ID = '77777777-7777-7777-7777-777777777777';

class FakeWebSocket {
  static OPEN = 1;

  static instances: FakeWebSocket[] = [];

  url: string;
  readyState = 0;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {
    this.readyState = 3;
    this.onclose?.();
  }

  open(): void {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.();
  }
}

describe('chatSocket', () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('передаёт task_id вместе с сообщением, не смешивая с текстом', () => {
    const socket = openChatSocket('55555555-5555-5555-5555-555555555555', {});
    const ws = FakeWebSocket.instances[0];
    ws.open();

    expect(socket?.send('Объясни условие', TASK_ID)).toBe(true);

    expect(JSON.parse(ws.sent[0])).toEqual({
      type: 'chat',
      content: 'Объясни условие',
      task_id: TASK_ID,
    });
  });

  it('без контекста задачи отправляет прежний протокол', () => {
    const socket = openChatSocket('55555555-5555-5555-5555-555555555555', {});
    const ws = FakeWebSocket.instances[0];
    ws.open();

    expect(socket?.send('Вопрос')).toBe(true);

    expect(JSON.parse(ws.sent[0])).toEqual({
      type: 'chat',
      content: 'Вопрос',
    });
  });

  it('не отправляет сообщение до открытия сокета', () => {
    const socket = openChatSocket('55555555-5555-5555-5555-555555555555', {});

    expect(socket?.send('Вопрос', TASK_ID)).toBe(false);
    expect(FakeWebSocket.instances[0].sent).toHaveLength(0);
  });
});
