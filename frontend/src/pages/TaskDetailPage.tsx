import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';

import { CodeEditor } from '@/components/code-editor/CodeEditor';
import { RecommendedTasks } from '@/components/tasks/RecommendedTasks';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { useTasksStore } from '@/store/tasks';
import type {
  AttemptDetail,
  AttemptItem,
  AttemptList,
  SubmitResponse,
} from '@/types/api';

/** Кнопка перехода в чат с контекстом задачи (S42-006) */
function AskAssistantLink({ taskId }: { taskId: string }) {
  const { t } = useTranslation();

  return (
    <Link
      to={`/chat?task=${taskId}`}
      className="inline-flex items-center rounded-lg border border-indigo-200 px-3 py-1.5 text-sm font-medium text-indigo-700 hover:bg-indigo-50"
    >
      {t('tasks.askAssistant')}
    </Link>
  );
}

function ResultsCard({
  result,
  taskId,
}: {
  result: SubmitResponse;
  taskId: string;
}) {
  const { t } = useTranslation();

  return (
    <Card title={result.practice ? t('tasks.checkResults') : t('tasks.results')}>
      <Alert tone={result.passed ? 'success' : 'warning'}>{result.message}</Alert>
      <p className="mt-2 text-sm text-slate-600">
        {t('tasks.passedOf', {
          passed: result.passed_count,
          total: result.total_count,
        })}
      </p>

      <ul className="mt-3 flex flex-col gap-2">
        {result.results.map((item) => (
          <li
            key={item.index}
            className={`rounded-lg border px-3 py-2 text-xs ${
              item.passed
                ? 'border-emerald-200 bg-emerald-50'
                : 'border-rose-200 bg-rose-50'
            }`}
          >
            <p className="font-medium">
              {t('tasks.case')} {item.index}:{' '}
              {item.passed ? t('tasks.casePassed') : t('tasks.caseFailed')}
              {item.description ? ` — ${item.description}` : ''}
            </p>
            {!item.passed && (
              <div className="mt-1 grid gap-1 font-mono">
                <span>in: {JSON.stringify(item.input)}</span>
                <span>expected: {JSON.stringify(item.expected_output)}</span>
                <span>actual: {JSON.stringify(item.actual_output)}</span>
                {item.error && <span className="text-rose-700">{item.error}</span>}
              </div>
            )}
          </li>
        ))}
      </ul>

      <div className="mt-3">
        <AskAssistantLink taskId={taskId} />
      </div>
    </Card>
  );
}

function DraftIndicator({
  savedAt,
  saving,
  onClear,
}: {
  savedAt: string | null;
  saving: boolean;
  onClear: () => void;
}) {
  const { t } = useTranslation();

  if (saving) {
    return (
      <p className="mt-2 text-xs text-slate-500" role="status">
        {t('tasks.draftSaving')}
      </p>
    );
  }

  if (!savedAt) {
    return null;
  }

  return (
    <p className="mt-2 flex items-center gap-2 text-xs text-slate-500">
      <span role="status">
        {t('tasks.draftSavedAt', {
          time: new Date(savedAt).toLocaleTimeString('ru-RU'),
        })}
      </span>
      <button
        type="button"
        className="text-indigo-700 hover:underline"
        onClick={onClear}
      >
        {t('tasks.draftDiscard')}
      </button>
    </p>
  );
}


function AttemptsHistory({
  attempts,
  attemptDetail,
  onOpen,
  onRestore,
}: {
  attempts: AttemptList | null;
  attemptDetail: AttemptDetail | null;
  onOpen: (attemptId: string) => void;
  onRestore: (code: string) => void;
}) {
  const { t } = useTranslation();

  if (!attempts || attempts.items.length === 0) {
    return null;
  }

  return (
    <Card title={t('tasks.attemptsHistory')}>
      <ul className="flex flex-col gap-2">
        {attempts.items.map((item: AttemptItem) => (
          <li
            key={item.id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm"
          >
            <span className="text-slate-600">
              {new Date(item.created_at).toLocaleString('ru-RU')}
            </span>
            <span
              className={item.passed ? 'font-medium text-emerald-700' : 'font-medium text-rose-700'}
            >
              {item.passed
                ? t('tasks.attemptPassed')
                : t('tasks.attemptFailed')}{' '}
              {t('tasks.attemptScore', {
                passed: item.passed_count,
                total: item.total_count,
              })}
            </span>
            <button
              type="button"
              className="text-sm text-indigo-700 hover:underline"
              onClick={() => onOpen(item.id)}
            >
              {t('tasks.attemptDetails')}
            </button>
          </li>
        ))}
      </ul>

      {attemptDetail && (
        <div className="mt-3 rounded-lg border border-indigo-200 bg-indigo-50 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium text-slate-800">
              {t('tasks.attemptDetails')}
            </p>
            <button
              type="button"
              className="text-sm text-indigo-700 hover:underline"
              onClick={() => onRestore(attemptDetail.code)}
            >
              {t('tasks.attemptRestore')}
            </button>
          </div>
          <pre className="mt-2 overflow-x-auto rounded bg-white p-2 font-mono text-xs">
            {attemptDetail.code}
          </pre>
          <ul className="mt-2 flex flex-col gap-1">
            {attemptDetail.results.map((result) => (
              <li
                key={result.index}
                className={`rounded border px-2 py-1 text-xs ${
                  result.passed
                    ? 'border-emerald-200 bg-emerald-50'
                    : 'border-rose-200 bg-rose-50'
                }`}
              >
                {t('tasks.case')} {result.index}:{' '}
                {result.passed ? t('tasks.casePassed') : t('tasks.caseFailed')}
                {!result.passed && (
                  <span className="ml-1 font-mono">
                    in: {JSON.stringify(result.input)} · expected:{' '}
                    {JSON.stringify(result.expected_output)} · actual:{' '}
                    {JSON.stringify(result.actual_output)}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}


export function TaskDetailPage() {
  const { t } = useTranslation();
  const { taskId = '' } = useParams<{ taskId: string }>();
  const detail = useTasksStore((state) => state.detail);
  const submission = useTasksStore((state) => state.submission);
  const checkResult = useTasksStore((state) => state.checkResult);
  const attempts = useTasksStore((state) => state.attempts);
  const attemptDetail = useTasksStore((state) => state.attemptDetail);
  const loading = useTasksStore((state) => state.loading);
  const submitting = useTasksStore((state) => state.submitting);
  const checking = useTasksStore((state) => state.checking);
  const error = useTasksStore((state) => state.error);
  const loadDetail = useTasksStore((state) => state.loadDetail);
  const submit = useTasksStore((state) => state.submit);
  const check = useTasksStore((state) => state.check);
  const loadAttempts = useTasksStore((state) => state.loadAttempts);
  const loadAttempt = useTasksStore((state) => state.loadAttempt);
  const draftSavedAt = useTasksStore((state) => state.draftSavedAt);
  const draftSaving = useTasksStore((state) => state.draftSaving);
  const saveDraft = useTasksStore((state) => state.saveDraft);
  const clearDraft = useTasksStore((state) => state.clearDraft);

  const [code, setCode] = useState('');
  const [hintsShown, setHintsShown] = useState(0);
  /** Код в редакторе отличается от сохранённого — нужен автосейв */
  const [dirty, setDirty] = useState(false);
  const draftTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function handleSubmit() {
    await submit(detail?.id ?? taskId, code);
    // Новая попытка появилась в истории — перечитываем список.
    void loadAttempts(taskId);
  }

  useEffect(() => {
    void loadDetail(taskId);
    void loadAttempts(taskId);
  }, [loadDetail, loadAttempts, taskId]);

  useEffect(() => {
    if (detail) {
      // Черновик важнее шаблона: работа ученика не должна теряться.
      setCode(detail.draft_code ?? detail.solution_template ?? '');
      setHintsShown(0);
      setDirty(false);
    }
  }, [detail]);

  // Автосохранение черновика: пауза в наборе 800 мс (S42-003).
  useEffect(() => {
    if (!dirty || !detail) {
      return;
    }
    if (draftTimer.current) {
      clearTimeout(draftTimer.current);
    }
    draftTimer.current = setTimeout(() => {
      void saveDraft(detail.id, code);
    }, 800);
    return () => {
      if (draftTimer.current) {
        clearTimeout(draftTimer.current);
      }
    };
  }, [code, dirty, detail, saveDraft]);

  // Уход со страницы не должен терять последние правки.
  useEffect(() => {
    const flush = () => {
      if (dirty && detail) {
        void saveDraft(detail.id, code);
      }
    };
    window.addEventListener('beforeunload', flush);
    return () => window.removeEventListener('beforeunload', flush);
  }, [code, dirty, detail, saveDraft]);

  if (loading && !detail) {
    return <Spinner />;
  }

  if (!detail) {
    return (
      <div className="flex flex-col gap-3">
        <Alert tone="error">{error ?? t('tasks.notFound')}</Alert>
        <Link to="/tasks" className="text-sm text-indigo-700 hover:underline">
          {t('tasks.backToList')}
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold text-slate-900">{detail.title}</h1>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
          {t(`tasks.difficulty.${detail.difficulty}`)}
        </span>
      </div>

      <Card>
        <p className="whitespace-pre-wrap text-sm text-slate-700">{detail.description}</p>
        <p className="mt-3 text-xs text-slate-500">
          {t('tasks.attempts')}: {detail.attempts} ·{' '}
          {t(`tasks.status.${detail.status}`)}
        </p>
        <div className="mt-3">
          <AskAssistantLink taskId={detail.id} />
        </div>
      </Card>

      {detail.hints.length > 0 && (
        <Card title={t('tasks.hints')}>
          <ul className="flex flex-col gap-2 text-sm text-slate-700">
            {detail.hints.slice(0, hintsShown).map((hint) => (
              <li key={hint} className="rounded-lg bg-amber-50 px-3 py-2">
                {hint}
              </li>
            ))}
          </ul>
          {hintsShown < detail.hints.length ? (
            <Button
              variant="secondary"
              className="mt-3"
              onClick={() => setHintsShown((value) => value + 1)}
            >
              {t('tasks.showHint')}
            </Button>
          ) : (
            <p className="mt-3 text-xs text-slate-500">{t('tasks.allHintsShown')}</p>
          )}
        </Card>
      )}

      <Card title={t('tasks.solution')}>
        <CodeEditor
          value={code}
          onChange={(value) => {
            setCode(value);
            setDirty(true);
          }}
          height="280px"
        />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button
            onClick={() => void handleSubmit()}
            loading={submitting}
            disabled={!code.trim()}
          >
            {t('tasks.submit')}
          </Button>
          <Button
            variant="secondary"
            onClick={() => void check(detail.id, code)}
            loading={checking}
            disabled={!code.trim()}
          >
            {t('tasks.check')}
          </Button>
          <Link to="/tasks" className="text-sm text-slate-600 hover:text-indigo-700">
            {t('tasks.backToList')}
          </Link>
        </div>
        <p className="mt-2 text-xs text-slate-500">{t('tasks.checkHint')}</p>
        <DraftIndicator
          savedAt={draftSavedAt}
          saving={draftSaving}
          onClear={() => {
            setDirty(false);
            void clearDraft(detail.id);
          }}
        />
      </Card>

      {error && <Alert tone="error">{error}</Alert>}

      <RecommendedTasks />

      <AttemptsHistory
        attempts={attempts}
        attemptDetail={attemptDetail}
        onOpen={(attemptId) => void loadAttempt(detail.id, attemptId)}
        onRestore={(restored) => setCode(restored)}
      />

      {checkResult && <ResultsCard result={checkResult} taskId={detail.id} />}
      {submission && <ResultsCard result={submission} taskId={detail.id} />}
    </div>
  );
}
