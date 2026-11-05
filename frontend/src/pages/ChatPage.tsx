import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';

import { ChatSearchPanel } from '@/components/chat/ChatSearchPanel';
import { LevelSelector } from '@/components/chat/LevelSelector';
import { MessageInput } from '@/components/chat/MessageInput';
import { MessageList } from '@/components/chat/MessageList';
import { SessionList } from '@/components/chat/SessionList';
import { TaskContextBanner } from '@/components/chat/TaskContextBanner';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { useChatSession } from '@/hooks/useChatSession';
import { saveBlob } from '@/lib/download';
import { templatesForLevel } from '@/lib/promptTemplates';
import { useAuthStore } from '@/store/auth';
import { useChatStore } from '@/store/chat';
import type { UserLevel } from '@/types/api';

export function ChatPage() {
  const { t } = useTranslation();
  const userLevel = useAuthStore((state) => state.user?.level ?? 'basic');
  const settings = useAuthStore((state) => state.user?.settings);
  const setPromptTemplate = useAuthStore((state) => state.setPromptTemplate);
  const sessions = useChatStore((state) => state.sessions);
  const active = useChatStore((state) => state.active);
  const draft = useChatStore((state) => state.draft);
  const streaming = useChatStore((state) => state.streaming);
  const loading = useChatStore((state) => state.loading);
  const error = useChatStore((state) => state.error);
  const taskContext = useChatStore((state) => state.taskContext);
  const loadSessions = useChatStore((state) => state.loadSessions);
  const createSession = useChatStore((state) => state.createSession);
  const openSession = useChatStore((state) => state.openSession);
  const deleteSession = useChatStore((state) => state.deleteSession);
  const renameSession = useChatStore((state) => state.renameSession);
  const togglePin = useChatStore((state) => state.togglePin);
  const regenerate = useChatStore((state) => state.regenerate);
  const exportMarkdown = useChatStore((state) => state.exportMarkdown);
  const reportError = useChatStore((state) => state.reportError);
  const feedback = useChatStore((state) => state.feedback);
  const setFeedback = useChatStore((state) => state.setFeedback);
  const clearFeedback = useChatStore((state) => state.clearFeedback);
  const loadTaskContext = useChatStore((state) => state.loadTaskContext);
  const clearTaskContext = useChatStore((state) => state.clearTaskContext);

  const [searchParams, setSearchParams] = useSearchParams();
  const taskParam = searchParams.get('task');

  const [level, setLevel] = useState<UserLevel>(userLevel);
  const [creating, setCreating] = useState(false);
  const [sessionsOpen, setSessionsOpen] = useState(false);

  const sessionId = active?.id ?? null;
  const { send, stop, connected } = useChatSession(sessionId);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  // Deep-link `/chat?task=<id>`: условие задачи подтягивается из API,
  // чтобы в плашке было название (S42-006).
  useEffect(() => {
    if (!taskParam) {
      clearTaskContext();
      return;
    }
    void loadTaskContext(taskParam);
  }, [taskParam, loadTaskContext, clearTaskContext]);

  function handleClearTaskContext() {
    clearTaskContext();
    const next = new URLSearchParams(searchParams);
    next.delete('task');
    setSearchParams(next, { replace: true });
  }

  async function handleCreate() {
    setCreating(true);
    try {
      const session = await createSession(level);
      await openSession(session.id);
    } finally {
      setCreating(false);
    }
  }

  // Шаблоны промптов — по уровню открытой сессии (или выбранному уровню).
  const activeLevel = (active?.level as UserLevel | undefined) ?? level;
  const templates = useMemo(() => templatesForLevel(activeLevel), [activeLevel]);
  const selectedTemplateId =
    typeof settings?.prompt_template === 'string' ? settings.prompt_template : null;

  async function handleDownloadMarkdown(sessionId: string) {
    const text = await exportMarkdown(sessionId);
    if (text !== null) {
      saveBlob(new Blob([text], { type: 'text/markdown;charset=utf-8' }), `chat-${sessionId.slice(0, 8)}.md`);
    }
  }

  async function handleCopyMarkdown(sessionId: string) {
    const text = await exportMarkdown(sessionId);
    if (text === null) {
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      reportError(t('errors.chatExport'));
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

        <ChatSearchPanel
          onOpenSession={(sessionId) => {
            void openSession(sessionId);
            setSessionsOpen(false);
          }}
        />

        <Button onClick={() => void handleCreate()} loading={creating}>
          {t('chat.newSession')}
        </Button>

        <div className="max-h-72 overflow-y-auto">
          <SessionList
            sessions={sessions}
            activeId={active?.id ?? null}
            onOpen={(sessionId) => {
              void openSession(sessionId);
              setSessionsOpen(false);
            }}
            onRename={(sessionId, title) => void renameSession(sessionId, title)}
            onTogglePin={(sessionId, pinned) =>
              void togglePin(sessionId, pinned)
            }
            onDelete={(sessionId) => void deleteSession(sessionId)}
            onDownloadMarkdown={(sessionId) => void handleDownloadMarkdown(sessionId)}
            onCopyMarkdown={(sessionId) => void handleCopyMarkdown(sessionId)}
          />
        </div>
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
            <h2 className="min-w-0 truncate text-sm font-semibold text-slate-700">
              {active
                ? (active.title ?? t('chat.title'))
                : t('chat.noSession')}
            </h2>
          </div>
          {active && !streaming && (
            <span
              className={`text-xs ${connected ? 'text-emerald-600' : 'text-amber-600'}`}
              title={connected ? t('chat.connected') : t('chat.disconnected')}
            >
              {connected ? '● live' : '○ rest'}
            </span>
          )}
          {streaming && (
            <Button onClick={stop} className="px-2 py-1 text-xs">
              {t('chat.stop')}
            </Button>
          )}
        </header>

        {taskContext && (
          <div className="border-b border-slate-200 px-4 py-2">
            <TaskContextBanner
              task={taskContext}
              onClear={handleClearTaskContext}
            />
          </div>
        )}

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
                onRegenerate={(messageId) => void regenerate(messageId)}
                feedback={feedback}
                onRate={(messageId, value) => void setFeedback(messageId, value)}
                onComment={(messageId, comment) =>
                  void setFeedback(
                    messageId,
                    feedback[messageId]?.value ?? -1,
                    comment,
                  )
                }
                onClearFeedback={(messageId) => void clearFeedback(messageId)}
              />
            </div>
            <MessageInput
              onSend={send}
              disabled={streaming}
              templates={templates}
              selectedTemplateId={selectedTemplateId}
              onSelectTemplate={(templateId) => void setPromptTemplate(templateId)}
            />
          </>
        )}
      </section>
    </div>
  );
}
