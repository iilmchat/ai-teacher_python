import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { LevelSelector } from '@/components/chat/LevelSelector';
import { MessageInput } from '@/components/chat/MessageInput';
import { MessageList } from '@/components/chat/MessageList';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { useChatSession } from '@/hooks/useChatSession';
import { useAuthStore } from '@/store/auth';
import { useChatStore } from '@/store/chat';
import type { UserLevel } from '@/types/api';

export function ChatPage() {
  const { t } = useTranslation();
  const userLevel = useAuthStore((state) => state.user?.level ?? 'basic');
  const sessions = useChatStore((state) => state.sessions);
  const active = useChatStore((state) => state.active);
  const draft = useChatStore((state) => state.draft);
  const streaming = useChatStore((state) => state.streaming);
  const loading = useChatStore((state) => state.loading);
  const error = useChatStore((state) => state.error);
  const loadSessions = useChatStore((state) => state.loadSessions);
  const createSession = useChatStore((state) => state.createSession);
  const openSession = useChatStore((state) => state.openSession);
  const deleteSession = useChatStore((state) => state.deleteSession);

  const [level, setLevel] = useState<UserLevel>(userLevel);
  const [creating, setCreating] = useState(false);
  const [sessionsOpen, setSessionsOpen] = useState(false);

  const sessionId = active?.id ?? null;
  const { send, connected } = useChatSession(sessionId);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  const sortedSessions = useMemo(
    () => [...sessions].sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [sessions],
  );

  async function handleCreate() {
    setCreating(true);
    try {
      const session = await createSession(level);
      await openSession(session.id);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
      {sessionsOpen && (
        <button
          type="button"
          aria-label={t('chat.closeSessions')}
          onClick={() => setSessionsOpen(false)}
          className="fixed inset-0 z-40 bg-slate-900/40 lg:hidden"
        />
      )}
      <aside
        id="sessions-panel"
        className={`${
          sessionsOpen
            ? 'fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] overflow-y-auto'
            : 'hidden'
        } flex-col gap-3 rounded-xl border border-slate-200 bg-white p-3 lg:static lg:z-auto lg:flex lg:w-auto`}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-700">
            {t('chat.sessions')}
          </h2>
          <button
            type="button"
            onClick={() => setSessionsOpen(false)}
            aria-label={t('chat.closeSessions')}
            className="rounded p-1 text-slate-500 hover:bg-slate-100 lg:hidden"
          >
            ✕
          </button>
        </div>

        <LevelSelector value={level} onChange={setLevel} disabled={creating} />

        <Button onClick={() => void handleCreate()} loading={creating}>
          {t('chat.newSession')}
        </Button>

        <ul className="flex max-h-72 flex-col gap-1 overflow-y-auto">
          {sortedSessions.map((session) => (
            <li key={session.id} className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => {
                  void openSession(session.id);
                  setSessionsOpen(false);
                }}
                aria-current={active?.id === session.id ? 'true' : undefined}
                className={`flex-1 truncate rounded-lg px-2 py-1.5 text-left text-xs ${
                  active?.id === session.id
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                {t(`levels.${session.level === 'advanced' ? 'advanced' : session.level}`)}
                {' · '}
                {new Date(session.created_at).toLocaleString('ru-RU')}
              </button>
              <button
                type="button"
                aria-label={t('chat.deleteSession')}
                onClick={() => void deleteSession(session.id)}
                className="rounded px-1 text-xs text-slate-400 hover:text-rose-600"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <section className="flex h-[70vh] flex-col overflow-hidden rounded-xl border border-slate-200 bg-white">
        <header className="flex items-center justify-between border-b border-slate-200 px-4 py-2">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setSessionsOpen(true)}
              aria-label={t('chat.openSessions')}
              aria-controls="sessions-panel"
              aria-expanded={sessionsOpen}
              className="rounded-lg px-2 py-1 text-sm text-slate-600 hover:bg-slate-100 lg:hidden"
            >
              ☰
            </button>
            <h2 className="text-sm font-semibold text-slate-700">
              {active ? t('chat.title') : t('chat.noSession')}
            </h2>
          </div>
          {active && (
            <span
              className={`text-xs ${connected ? 'text-emerald-600' : 'text-amber-600'}`}
              title={connected ? t('chat.connected') : t('chat.disconnected')}
            >
              {connected ? '● live' : '○ rest'}
            </span>
          )}
        </header>

        {error && (
          <div className="p-3">
            <Alert tone="error">{error}</Alert>
          </div>
        )}

        {loading && !active && <Spinner />}

        {!active && !loading && (
          <div className="flex flex-1 items-center justify-center p-6 text-center text-sm text-slate-500">
            {t('chat.createFirst')}
          </div>
        )}

        {active && (
          <>
            <div className="flex-1 overflow-hidden">
              <MessageList
                messages={active.messages}
                draft={draft}
                streaming={streaming}
              />
            </div>
            <MessageInput onSend={send} disabled={streaming} />
          </>
        )}
      </section>
    </div>
  );
}
