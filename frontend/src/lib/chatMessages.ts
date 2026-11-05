/**
 * Помощники по сообщениям чата.
 */

import type { ChatMessage } from '@/types/api';

/**
 * Ответ ассистента остановлен учеником (S43-002).
 *
 * Сервер помечает такой ответ в `message_metadata` полем `stopped`, а
 * клиент добавляет то же поле локальному сообщению.
 */
export function isStoppedMessage(message: ChatMessage): boolean {
  const metadata = message.metadata as { stopped?: unknown } | undefined;
  return metadata?.stopped === true;
}
