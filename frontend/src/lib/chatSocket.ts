/**
 * Клиент WebSocket чата со стримингом ответа ассистента.
 *
 * Протокол backend:
 *   client → {"type":"chat","content":"...","task_id"?:"<uuid>"} | {"type":"ping"}
 *   server → {"type":"start"|"token"|"done"|"error"|"pong", content?, detail?,
 *             warnings?}
 *
 * `task_id` (S42-006) — контекст задачи: backend кладёт условие в отдельное
 * системное сообщение, а в историю — только метаданные вопроса.
 */

import i18n from '@/i18n';
import { getAccessToken } from '@/lib/token';

export interface ChatSocketHandlers {
  onStart?: () => void;
  onToken?: (delta: string) => void;
  onDone?: (full: string, warnings: string[]) => void;
  onError?: (detail: string) => void;
  onOpen?: () => void;
  onClose?: () => void;
}

export interface ChatSocket {
  send: (content: string, taskId?: string | null) => boolean;
  close: () => void;
  readonly ready: boolean;
}

function buildWsUrl(sessionId: string): string {
  const base = import.meta.env.VITE_WS_BASE;
  if (base) {
    return `${base}/api/v1/chat/ws/${sessionId}?token=${encodeURIComponent(
      getAccessToken() ?? '',
    )}`;
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/api/v1/chat/ws/${sessionId}?token=${encodeURIComponent(
    getAccessToken() ?? '',
  )}`;
}

/** Открыть сокет чата. Возвращает null, если WebSocket недоступен. */
export function openChatSocket(
  sessionId: string,
  handlers: ChatSocketHandlers,
): ChatSocket | null {
  if (typeof WebSocket === 'undefined') {
    return null;
  }

  let ready = false;
  const socket = new WebSocket(buildWsUrl(sessionId));

  socket.onopen = () => {
    ready = true;
    handlers.onOpen?.();
  };

  socket.onmessage = (event: MessageEvent<string>) => {
    let payload: {
      type?: string;
      content?: string;
      detail?: string;
      warnings?: unknown;
    };
    try {
      payload = JSON.parse(event.data) as typeof payload;
    } catch {
      return;
    }

    switch (payload.type) {
      case 'start':
        handlers.onStart?.();
        break;
      case 'token':
        handlers.onToken?.(payload.content ?? '');
        break;
      case 'done': {
        const warnings = Array.isArray(payload.warnings)
          ? payload.warnings.filter(
              (item): item is string => typeof item === 'string',
            )
          : [];
        handlers.onDone?.(payload.content ?? '', warnings);
        break;
      }
      case 'error':
        handlers.onError?.(payload.detail ?? i18n.t('errors.chat'));
        break;
      default:
        break;
    }
  };

  socket.onclose = () => {
    ready = false;
    handlers.onClose?.();
  };

  socket.onerror = () => {
    ready = false;
    handlers.onError?.(i18n.t('errors.chatConnect'));
  };

  return {
    send(content: string, taskId?: string | null): boolean {
      if (!ready || socket.readyState !== WebSocket.OPEN) {
        return false;
      }
      const payload = taskId
        ? { type: 'chat', content, task_id: taskId }
        : { type: 'chat', content };
      socket.send(JSON.stringify(payload));
      return true;
    },
    close() {
      ready = false;
      socket.close();
    },
    get ready() {
      return ready;
    },
  };
}
