import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import type { MessageFeedback } from '@/types/api';

interface MessageFeedbackProps {
  messageId: string;
  /** Моя оценка ответа, если она уже есть */
  feedback?: MessageFeedback;
  /** Поставить оценку (+1 / −1) */
  onRate: (messageId: string, value: 1 | -1) => void;
  /** Сохранить комментарий к оценке */
  onComment: (messageId: string, comment: string) => void;
  /** Снять оценку */
  onClear?: (messageId: string) => void;
}

/** Оценка ответа ассистента: 👍/👎 и комментарий (S43-003) */
export function MessageFeedbackButtons({
  messageId,
  feedback,
  onRate,
  onComment,
  onClear,
}: MessageFeedbackProps) {
  const { t } = useTranslation();
  const [commentOpen, setCommentOpen] = useState(false);
  const [draft, setDraft] = useState(feedback?.comment ?? '');

  function handleRate(value: 1 | -1) {
    onRate(messageId, value);
    // К негативной оценке комментарий полезнее всего — открываем поле.
    if (value === -1) {
      setCommentOpen(true);
    }
  }

  function saveComment() {
    onComment(messageId, draft.trim());
    setCommentOpen(false);
  }

  return (
    <div className="mt-2 flex flex-wrap items-center gap-1">
      <button
        type="button"
        onClick={() => handleRate(1)}
        aria-label={t('chat.feedbackLike')}
        aria-pressed={feedback?.value === 1}
        className={`rounded px-1.5 py-0.5 text-xs ${
          feedback?.value === 1
            ? 'bg-emerald-100 text-emerald-700'
            : 'text-slate-500 hover:bg-white'
        }`}
      >
        👍
      </button>
      <button
        type="button"
        onClick={() => handleRate(-1)}
        aria-label={t('chat.feedbackDislike')}
        aria-pressed={feedback?.value === -1}
        className={`rounded px-1.5 py-0.5 text-xs ${
          feedback?.value === -1
            ? 'bg-rose-100 text-rose-700'
            : 'text-slate-500 hover:bg-white'
        }`}
      >
        👎
      </button>
      {feedback && (
        <>
          <button
            type="button"
            onClick={() => setCommentOpen((open) => !open)}
            aria-label={t('chat.feedbackComment')}
            className="rounded px-1.5 py-0.5 text-xs text-slate-500 hover:bg-white"
          >
            💬
          </button>
          {onClear && (
            <button
              type="button"
              onClick={() => onClear(messageId)}
              aria-label={t('chat.feedbackClear')}
              className="rounded px-1.5 py-0.5 text-xs text-slate-400 hover:bg-white hover:text-rose-600"
            >
              ✕
            </button>
          )}
        </>
      )}
      {commentOpen && (
        <div className="mt-1 flex w-full flex-col gap-1">
          <label htmlFor={`feedback-${messageId}`} className="sr-only">
            {t('chat.feedbackCommentLabel')}
          </label>
          <textarea
            id={`feedback-${messageId}`}
            rows={2}
            value={draft}
            maxLength={500}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={t('chat.feedbackCommentLabel')}
            className="w-full resize-y rounded-lg border border-slate-300 px-2 py-1 text-xs outline-none focus:border-indigo-500"
          />
          <div className="flex gap-1">
            <button
              type="button"
              onClick={saveComment}
              className="rounded bg-indigo-600 px-2 py-0.5 text-xs text-white hover:bg-indigo-700"
            >
              {t('chat.feedbackSave')}
            </button>
            <button
              type="button"
              onClick={() => setCommentOpen(false)}
              className="rounded px-2 py-0.5 text-xs text-slate-600 hover:bg-white"
            >
              {t('chat.cancel')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
