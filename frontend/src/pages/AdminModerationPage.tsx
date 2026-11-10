import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Modal } from '@/components/ui/Modal';
import { Spinner } from '@/components/ui/Spinner';
import { Table, Td, Th, Tr } from '@/components/ui/Table';
import { api } from '@/lib/api';
import type {
  AdminTaskReviewItem,
  AdminTaskReviewResponse,
  ModerationAction,
  ModerationSource,
  TaskDifficulty,
  TaskModerateResponse,
} from '@/types/api';

const SOURCES: ModerationSource[] = ['generated', 'imported'];
const DIFFICULTIES: TaskDifficulty[] = ['easy', 'medium', 'hard'];
const THRESHOLDS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

const SUCCESS_KEYS: Record<ModerationAction, string> = {
  publish: 'publishSuccess',
  unpublish: 'unpublishSuccess',
  return_to_revision: 'returnSuccess',
};

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function AdminModerationPage() {
  const { t } = useTranslation();

  const [items, setItems] = useState<AdminTaskReviewItem[]>([]);
  const [total, setTotal] = useState(0);
  const [source, setSource] = useState<ModerationSource | ''>('');
  const [difficulty, setDifficulty] = useState<TaskDifficulty | ''>('');
  const [threshold, setThreshold] = useState(3);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState<ModerationAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [revisionOpen, setRevisionOpen] = useState(false);
  const [comment, setComment] = useState('');
  const [commentError, setCommentError] = useState<string | null>(null);

  const loadQueue = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (source) {
        params.set('source', source);
      }
      if (difficulty) {
        params.set('difficulty', difficulty);
      }
      params.set('threshold', String(threshold));
      const data = await api.get<AdminTaskReviewResponse>(
        `/admin/tasks/review?${params.toString()}`,
      );
      setItems(data.items);
      setTotal(data.total);
      setSelectedId((current) =>
        current && data.items.some((item) => item.id === current)
          ? current
          : (data.items[0]?.id ?? null),
      );
    } catch {
      setError(t('moderation.loadError'));
    } finally {
      setLoading(false);
    }
  }, [difficulty, source, t, threshold]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  const selected = items.find((item) => item.id === selectedId) ?? null;

  function openRevision() {
    setComment('');
    setCommentError(null);
    setRevisionOpen(true);
  }

  async function runAction(kind: ModerationAction) {
    if (!selected) {
      return;
    }
    if (kind === 'return_to_revision' && !comment.trim()) {
      setCommentError(t('moderation.commentRequired'));
      return;
    }
    setAction(kind);
    setError(null);
    setNotice(null);
    try {
      const payload =
        kind === 'return_to_revision'
          ? { action: kind, comment: comment.trim() }
          : { action: kind };
      await api.post<TaskModerateResponse>(
        `/admin/tasks/${selected.id}/moderate`,
        payload,
      );
      setNotice(t(`moderation.${SUCCESS_KEYS[kind]}`));
      setRevisionOpen(false);
      setComment('');
      setCommentError(null);
      await loadQueue();
    } catch {
      setError(t('moderation.actionError'));
    } finally {
      setAction(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">
            {t('moderation.title')}
          </h1>
          <p className="mt-1 text-sm text-slate-500">{t('moderation.subtitle')}</p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/admin" className="text-sm text-indigo-700 hover:underline">
            {t('moderation.back')}
          </Link>
          <Button variant="secondary" onClick={() => void loadQueue()} loading={loading}>
            {t('moderation.refresh')}
          </Button>
        </div>
      </div>

      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      <Card title={t('moderation.filters')}>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-slate-700">{t('moderation.source')}</span>
            <select
              value={source}
              onChange={(event) =>
                setSource(event.target.value as ModerationSource | '')
              }
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">{t('moderation.sourceAll')}</option>
              {SOURCES.map((value) => (
                <option key={value} value={value}>
                  {t(`moderation.sources.${value}`)}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-slate-700">
              {t('moderation.difficulty')}
            </span>
            <select
              value={difficulty}
              onChange={(event) =>
                setDifficulty(event.target.value as TaskDifficulty | '')
              }
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">{t('moderation.difficultyAll')}</option>
              {DIFFICULTIES.map((value) => (
                <option key={value} value={value}>
                  {t(`tasks.difficulty.${value}`)}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-slate-700">
              {t('moderation.threshold')}
            </span>
            <select
              value={threshold}
              onChange={(event) => setThreshold(Number(event.target.value))}
              aria-describedby="moderation-threshold-hint"
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              {THRESHOLDS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
            <span id="moderation-threshold-hint" className="text-xs text-slate-500">
              {t('moderation.thresholdHint')}
            </span>
          </label>
        </div>
      </Card>

      {loading && !items.length && <Spinner />}

      <Card title={t('moderation.queue')}>
        <p className="mb-3 text-xs text-slate-500">
          {t('moderation.queueTotal', { count: total })}
        </p>
        {!loading && items.length === 0 ? (
          <p className="py-4 text-center text-sm text-slate-500">
            {t('moderation.empty')}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <thead className="text-xs uppercase text-slate-500">
                <Tr>
                  <Th className="py-2">{t('moderation.colTask')}</Th>
                  <Th className="py-2">{t('moderation.colSource')}</Th>
                  <Th className="py-2">{t('moderation.colDifficulty')}</Th>
                  <Th className="py-2">{t('moderation.colStatus')}</Th>
                  <Th className="py-2">{t('moderation.colAttempts')}</Th>
                  <Th className="py-2">{t('moderation.colSuccess')}</Th>
                  <Th className="py-2">{t('moderation.colStudents')}</Th>
                  <Th className="py-2">{t('moderation.colStuck')}</Th>
                  <Th className="py-2">{t('moderation.colActions')}</Th>
                </Tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <Tr
                    key={item.id}
                    className={`border-t border-slate-100 ${
                      item.id === selectedId ? 'bg-indigo-50/50' : ''
                    }`}
                  >
                    <Td className="py-2 font-medium text-slate-800">{item.title}</Td>
                    <Td className="py-2">{t(`moderation.sources.${item.source}`)}</Td>
                    <Td className="py-2">{t(`tasks.difficulty.${item.difficulty}`)}</Td>
                    <Td className="py-2">
                      {item.is_active
                        ? t('moderation.statusActive')
                        : t('moderation.statusHidden')}
                    </Td>
                    <Td className="py-2">{item.metrics.attempts}</Td>
                    <Td className="py-2">{percent(item.metrics.success_rate)}</Td>
                    <Td className="py-2">{item.metrics.students}</Td>
                    <Td className="py-2">{item.metrics.stuck_students}</Td>
                    <Td className="py-2">
                      <Button
                        variant="ghost"
                        aria-label={`${t('moderation.open')}: ${item.title}`}
                        onClick={() => setSelectedId(item.id)}
                      >
                        {t('moderation.open')}
                      </Button>
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}
      </Card>

      {selected && (
        <Card title={t('moderation.cardTitle')}>
          <div className="flex flex-col gap-4">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-semibold text-slate-900">
                  {selected.title}
                </h2>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                  {t(`moderation.sources.${selected.source}`)}
                </span>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                  {t(`tasks.difficulty.${selected.difficulty}`)}
                </span>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs ${
                    selected.is_active
                      ? 'bg-emerald-100 text-emerald-700'
                      : 'bg-amber-100 text-amber-700'
                  }`}
                >
                  {selected.is_active
                    ? t('moderation.statusActive')
                    : t('moderation.statusHidden')}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {selected.category} ·{' '}
                {t('admin.casesCount', { count: selected.test_cases_count })}
              </p>
              <p className="mt-3 whitespace-pre-line text-sm text-slate-700">
                {selected.description}
              </p>
            </div>

            {selected.moderation_comment && (
              <Alert tone="warning">
                <span className="font-medium">
                  {t('moderation.moderationComment')}:
                </span>{' '}
                {selected.moderation_comment}
              </Alert>
            )}

            <div>
              <h3 className="text-sm font-semibold text-slate-800">
                {t('moderation.metricsTitle')}
              </h3>
              <div className="mt-2 grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="text-xs text-slate-500">{t('moderation.metricAttempts')}</p>
                  <p className="mt-1 text-lg font-semibold text-slate-900">
                    {selected.metrics.attempts}
                  </p>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="text-xs text-slate-500">{t('moderation.metricSuccess')}</p>
                  <p className="mt-1 text-lg font-semibold text-slate-900">
                    {percent(selected.metrics.success_rate)}
                  </p>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="text-xs text-slate-500">{t('moderation.metricAvg')}</p>
                  <p className="mt-1 text-lg font-semibold text-slate-900">
                    {selected.metrics.avg_attempts.toFixed(2)}
                  </p>
                </div>
                <div className="rounded-lg bg-slate-50 p-3">
                  <p className="text-xs text-slate-500">{t('moderation.metricStudents')}</p>
                  <p className="mt-1 text-lg font-semibold text-slate-900">
                    {selected.metrics.students}
                  </p>
                </div>
                <div className="rounded-lg bg-rose-50 p-3">
                  <p className="text-xs text-rose-600">
                    {t('moderation.metricStuck', { threshold })}
                  </p>
                  <p className="mt-1 text-lg font-semibold text-rose-700">
                    {selected.metrics.stuck_students}
                  </p>
                </div>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-slate-800">
                {t('moderation.recentTitle')}
              </h3>
              {selected.recent_attempts.length === 0 ? (
                <p className="mt-1 text-sm text-slate-500">
                  {t('moderation.recentEmpty')}
                </p>
              ) : (
                <div className="mt-2 overflow-x-auto">
                  <Table>
                    <thead className="text-xs uppercase text-slate-500">
                      <Tr>
                        <Th className="py-2">{t('moderation.colStudent')}</Th>
                        <Th className="py-2">{t('moderation.colResult')}</Th>
                        <Th className="py-2">{t('moderation.colDate')}</Th>
                      </Tr>
                    </thead>
                    <tbody>
                      {selected.recent_attempts.map((attempt) => (
                        <Tr key={attempt.id} className="border-t border-slate-100">
                          <Td className="py-2">{attempt.username}</Td>
                          <Td className="py-2">
                            {attempt.passed
                              ? t('moderation.resultPassed')
                              : t('moderation.resultFailed')}
                          </Td>
                          <Td className="py-2">
                            {new Date(attempt.created_at).toLocaleString()}
                          </Td>
                        </Tr>
                      ))}
                    </tbody>
                  </Table>
                </div>
              )}
            </div>

            <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-3">
              <Button
                onClick={() => void runAction('publish')}
                loading={action === 'publish'}
                disabled={selected.is_active}
              >
                {t('moderation.publish')}
              </Button>
              <Button
                variant="secondary"
                onClick={() => void runAction('unpublish')}
                loading={action === 'unpublish'}
                disabled={!selected.is_active}
              >
                {t('moderation.unpublish')}
              </Button>
              <Button
                variant="danger"
                onClick={openRevision}
                loading={action === 'return_to_revision'}
              >
                {t('moderation.returnToRevision')}
              </Button>
            </div>
          </div>
        </Card>
      )}

      <Modal
        open={revisionOpen}
        title={t('moderation.revisionTitle')}
        onClose={() => setRevisionOpen(false)}
        closeLabel={t('moderation.cancel')}
        footer={
          <>
            <Button variant="secondary" onClick={() => setRevisionOpen(false)}>
              {t('moderation.cancel')}
            </Button>
            <Button
              variant="danger"
              onClick={() => void runAction('return_to_revision')}
              loading={action === 'return_to_revision'}
            >
              {t('moderation.confirmReturn')}
            </Button>
          </>
        }
      >
        <p className="text-sm text-slate-600">{t('moderation.revisionHint')}</p>
        <label
          htmlFor="moderation-comment"
          className="mt-3 block text-sm font-medium text-slate-700"
        >
          {t('moderation.commentLabel')}
        </label>
        <textarea
          id="moderation-comment"
          value={comment}
          maxLength={1000}
          rows={4}
          placeholder={t('moderation.commentPlaceholder')}
          aria-invalid={commentError ? true : undefined}
          aria-describedby="moderation-comment-hint"
          onChange={(event) => {
            setComment(event.target.value);
            setCommentError(null);
          }}
          className={`mt-1 w-full rounded-lg border px-3 py-2 text-sm shadow-sm outline-none focus:border-indigo-500 ${
            commentError ? 'border-rose-400' : 'border-slate-300'
          }`}
        />
        <div className="mt-1 flex items-center justify-between text-xs">
          <span id="moderation-comment-hint" className="text-slate-500">
            {t('moderation.commentCounter', { count: comment.length })}
          </span>
          {commentError && (
            <span role="alert" className="text-rose-600">
              {commentError}
            </span>
          )}
        </div>
      </Modal>
    </div>
  );
}
