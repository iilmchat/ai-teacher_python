import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

import { MessageFeedbackButtons } from '@/components/chat/MessageFeedback';
import { RichText } from '@/components/chat/RichText';
import { isStoppedMessage } from '@/lib/chatMessages';
import type { ChatMessage, MessageFeedback } from '@/types/api';

interface MessageListProps {
  messages: ChatMessage[];
  draft?: string;
  streaming?: boolean;
  /** Перегенерировать ответ ассистента (S43-002) */
  onRegenerate?: (messageId: string) => void;
  /** Мои оценки ответов: id сообщения → оценка (S43-003) */
  feedback?: Record<string, MessageFeedback>;
  /** Поставить оценку ответа */
  onRate?: (messageId: string, value: 1 | -1) => void;
  /** Сохранить комментарий к оценке */
  onComment?: (messageId: string, comment: string) => void;
  /** Снять оценку */
  onClearFeedback?: (messageId: string) => void;
}

export function MessageList({
  messages,
  draft = '',
  streaming = false,
  onRegenerate,
  feedback,
  onRate,
  onComment,
  onClearFeedback,
}: MessageListProps) {
  const { t } = useTranslation();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // scrollIntoView не реализован в jsdom — вызываем только если доступен
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth' });
  }, [messages.length, draft, streaming]);

  if (messages.length === 0 && !streaming) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-sm text-slate-500">
        {t('chat.emptyState')}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 overflow-y-auto p-4" data-testid="message-list">
      {messages.map((message) => (
        <article
          key={message.id}
          className={`max-w-[85%] rounded-xl px-4 py-2.5 text-sm ${
            message.role === 'user'
              ? 'self-end bg-indigo-600 text-white'
              : 'self-start bg-slate-100 text-slate-900'
          }`}
        >
          <RichText text={message.content} />
          {message.role === 'assistant' && (message.warnings?.length ?? 0) > 0 && (
            <p className="mt-2 rounded bg-amber-100 px-2 py-1 text-xs text-amber-800" role="status">
              {t('chat.policyWarning')}
            </p>
          )}
          {message.role === 'assistant' && isStoppedMessage(message) && (
            <p className="mt-2 rounded bg-slate-200 px-2 py-1 text-xs text-slate-700" role="status">
              {t('chat.stopped')}
            </p>
          )}
          {message.role === 'assistant' && onRegenerate && (
            <button
              type="button"
              onClick={() => onRegenerate(message.id)}
              aria-label={t('chat.regenerate')}
              className="mt-2 rounded px-1.5 py-0.5 text-xs text-slate-500 hover:bg-white hover:text-indigo-700"
            >
              {t('chat.regenerate')}
            </button>
          )}
          {message.role === 'assistant' && onRate && onComment && (
            <MessageFeedbackButtons
              messageId={message.id}
              feedback={feedback?.[message.id]}
              onRate={onRate}
              onComment={onComment}
              onClear={onClearFeedback}
            />
          )}
        </article>
      ))}

      {(streaming || draft) && (
        <article className="max-w-[85%] self-start rounded-xl bg-slate-100 px-4 py-2.5 text-sm text-slate-900">
          <RichText text={draft} />
          {streaming && (
            <span className="ml-1 inline-block animate-pulse text-slate-500">▍</span>
          )}
        </article>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
