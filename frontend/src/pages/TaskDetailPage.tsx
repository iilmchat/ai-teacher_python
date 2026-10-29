import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';

import { CodeEditor } from '@/components/code-editor/CodeEditor';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { useTasksStore } from '@/store/tasks';

export function TaskDetailPage() {
  const { t } = useTranslation();
  const { taskId = '' } = useParams<{ taskId: string }>();
  const detail = useTasksStore((state) => state.detail);
  const submission = useTasksStore((state) => state.submission);
  const loading = useTasksStore((state) => state.loading);
  const submitting = useTasksStore((state) => state.submitting);
  const error = useTasksStore((state) => state.error);
  const loadDetail = useTasksStore((state) => state.loadDetail);
  const submit = useTasksStore((state) => state.submit);

  const [code, setCode] = useState('');
  const [hintsShown, setHintsShown] = useState(0);

  useEffect(() => {
    void loadDetail(taskId);
  }, [loadDetail, taskId]);

  useEffect(() => {
    if (detail) {
      setCode(detail.solution_template ?? '');
      setHintsShown(0);
    }
  }, [detail]);

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
      <div className="flex items-center justify-between">
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
        <CodeEditor value={code} onChange={setCode} height="280px" />
        <div className="mt-3 flex items-center gap-3">
          <Button
            onClick={() => void submit(detail.id, code)}
            loading={submitting}
            disabled={!code.trim()}
          >
            {t('tasks.submit')}
          </Button>
          <Link to="/tasks" className="text-sm text-slate-600 hover:text-indigo-700">
            {t('tasks.backToList')}
          </Link>
        </div>
      </Card>

      {error && <Alert tone="error">{error}</Alert>}

      {submission && (
        <Card title={t('tasks.results')}>
          <Alert tone={submission.passed ? 'success' : 'warning'}>
            {submission.message}
          </Alert>
          <p className="mt-2 text-sm text-slate-600">
            {t('tasks.passedOf', {
              passed: submission.passed_count,
              total: submission.total_count,
            })}
          </p>

          <ul className="mt-3 flex flex-col gap-2">
            {submission.results.map((result) => (
              <li
                key={result.index}
                className={`rounded-lg border px-3 py-2 text-xs ${
                  result.passed
                    ? 'border-emerald-200 bg-emerald-50'
                    : 'border-rose-200 bg-rose-50'
                }`}
              >
                <p className="font-medium">
                  {t('tasks.case')} {result.index}:{' '}
                  {result.passed ? t('tasks.casePassed') : t('tasks.caseFailed')}
                  {result.description ? ` — ${result.description}` : ''}
                </p>
                {!result.passed && (
                  <div className="mt-1 grid gap-1 font-mono">
                    <span>in: {JSON.stringify(result.input)}</span>
                    <span>expected: {JSON.stringify(result.expected_output)}</span>
                    <span>actual: {JSON.stringify(result.actual_output)}</span>
                    {result.error && <span className="text-rose-700">{result.error}</span>}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
