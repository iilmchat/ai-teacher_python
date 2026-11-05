import { type KeyboardEvent, useState } from 'react';
import { useTranslation } from 'react-i18next';

import type { ChatSession } from '@/types/api';

interface SessionListProps {
  sessions: ChatSession[];
  activeId: string | null;
  onOpen: (sessionId: string) => void;
  onRename: (sessionId: string, title: string) => void;
  onTogglePin: (sessionId: string, pinned: boolean) => void;
  onDelete: (sessionId: string) => void;
  /** Скачать диалог в Markdown (S43-004) */
  onDownloadMarkdown?: (sessionId: string) => void;
  /** Скопировать диалог в Markdown (S43-004) */
  onCopyMarkdown?: (sessionId: string) => void;
}

/** Список сессий чата: заголовки, переименование, закрепление, удаление (S43-001) */
export function SessionList({
  sessions,
  activeId,
  onOpen,
  onRename,
  onTogglePin,
  onDelete,
  onDownloadMarkdown,
  onCopyMarkdown,
}: SessionListProps) {
  const { t } = useTranslation();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState('');

  function startRename(session: ChatSession) {
    setEditingId(session.id);
    setDraft(session.title ?? '');
  }

  function cancelRename() {
    setEditingId(null);
    setDraft('');
  }

  function submitRename(session: ChatSession) {
    const title = draft.trim();
    if (!title) {
      return;
    }
    onRename(session.id, title);
    cancelRename();
  }

  function handleKeyDown(
    event: KeyboardEvent<HTMLInputElement>,
    session: ChatSession,
  ) {
    if (event.key === 'Enter') {
      event.preventDefault();
      submitRename(session);
    } else if (event.key === 'Escape') {
      cancelRename();
    }
  }

  function confirmDelete(session: ChatSession) {
    const title = session.title ?? t('chat.untitled');
    if (window.confirm(t('chat.deleteConfirm', { title }))) {
      onDelete(session.id);
    }
  }

  if (sessions.length === 0) {
    return null;
  }

  return (
    <ul aria-label={t('chat.sessions')} className="flex flex-col gap-1">
      {sessions.map((session) => {
        const title = session.title ?? t('chat.untitled');
        const isActive = activeId === session.id;
        const isEditing = editingId === session.id;

        return (
          <li
            key={session.id}
            className={`flex flex-col gap-1 rounded-lg px-2 py-1.5 text-xs ${
              isActive ? 'bg-indigo-50' : 'hover:bg-slate-100'
            }`}
          >
            {isEditing ? (
              <div className="flex items-center gap-1">
                <label htmlFor={`session-title-${session.id}`} className="sr-only">
                  {t('chat.sessionTitleLabel')}
                </label>
                <input
                  id={`session-title-${session.id}`}
                  autoFocus
                  value={draft}
                  maxLength={120}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={(event) => handleKeyDown(event, session)}
                  className="min-w-0 flex-1 rounded border border-slate-300 px-1.5 py-1 text-xs focus:border-indigo-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
                />
                <button
                  type="button"
                  onClick={() => submitRename(session)}
                  disabled={!draft.trim()}
                  aria-label={t('chat.saveTitle')}
                  className="rounded px-1 text-emerald-700 hover:bg-emerald-50 disabled:opacity-40"
                >
                  ✓
                </button>
                <button
                  type="button"
                  onClick={cancelRename}
                  aria-label={t('chat.cancel')}
                  className="rounded px-1 text-slate-500 hover:bg-slate-200"
                >
                  ✕
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => onOpen(session.id)}
                  aria-current={isActive ? 'true' : undefined}
                  title={title}
                  className={`min-w-0 flex-1 truncate text-left ${
                    isActive ? 'font-medium text-indigo-700' : 'text-slate-700'
                  }`}
                >
                  {session.pinned && (
                    <span aria-label={t('chat.pinned')} className="mr-1">
                      📌
                    </span>
                  )}
                  {title}
                  <span className="block truncate text-[10px] text-slate-400">
                    {t(`levels.${session.level}`)} ·{' '}
                    {new Date(session.created_at).toLocaleString('ru-RU')}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => startRename(session)}
                  aria-label={`${t('chat.renameSession')}: ${title}`}
                  className="rounded px-1 text-slate-400 hover:text-indigo-600"
                >
                  ✎
                </button>
                <button
                  type="button"
                  onClick={() => onTogglePin(session.id, !session.pinned)}
                  aria-label={`${
                    session.pinned ? t('chat.unpinSession') : t('chat.pinSession')
                  }: ${title}`}
                  aria-pressed={session.pinned}
                  className={`rounded px-1 ${
                    session.pinned
                      ? 'text-amber-600 hover:text-amber-700'
                      : 'text-slate-400 hover:text-amber-600'
                  }`}
                >
                  📌
                </button>
                <button
                  type="button"
                  onClick={() => confirmDelete(session)}
                  aria-label={`${t('chat.deleteSession')}: ${title}`}
                  className="rounded px-1 text-slate-400 hover:text-rose-600"
                >
                  ✕
                </button>
              </div>
            )}
            {isActive && (onDownloadMarkdown || onCopyMarkdown) && (
              <div className="flex items-center gap-2 pl-1 pt-1 text-[11px]">
                {onDownloadMarkdown && (
                  <button
                    type="button"
                    onClick={() => onDownloadMarkdown(session.id)}
                    aria-label={`${t('chat.downloadMarkdown')}: ${title}`}
                    className="rounded px-1 text-slate-500 hover:text-indigo-700"
                  >
                    {t('chat.downloadMarkdown')}
                  </button>
                )}
                {onCopyMarkdown && (
                  <button
                    type="button"
                    onClick={() => onCopyMarkdown(session.id)}
                    aria-label={`${t('chat.copyMarkdown')}: ${title}`}
                    className="rounded px-1 text-slate-500 hover:text-indigo-700"
                  >
                    {t('chat.copyMarkdown')}
                  </button>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
