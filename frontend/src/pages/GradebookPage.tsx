import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { Table, Td, Th, Tr } from '@/components/ui/Table';
import { api } from '@/lib/api';
import { saveBlob } from '@/lib/download';
import type { GradebookResponse } from '@/types/api';

const STATUS_KEYS: Record<string, string> = {
  not_started: 'classrooms.gradebook.statusNotStarted',
  in_progress: 'classrooms.gradebook.statusInProgress',
  completed: 'classrooms.gradebook.statusCompleted',
};

export function GradebookPage() {
  const { t } = useTranslation();
  const { classroomId = '' } = useParams();
  const [data, setData] = useState<GradebookResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.get<GradebookResponse>(`/classrooms/${classroomId}/gradebook`));
    } catch {
      setError(t('classrooms.gradebook.loadError'));
    } finally {
      setLoading(false);
    }
  }, [classroomId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const cells = useMemo(() => {
    const map = new Map<string, GradebookResponse['cells'][number]>();
    for (const cell of data?.cells ?? []) {
      map.set(`${cell.student_id}:${cell.task_id}`, cell);
    }
    return map;
  }, [data]);

  async function downloadCsv() {
    setDownloading(true);
    setError(null);
    try {
      const blob = await api.download(`/classrooms/${classroomId}/gradebook/csv`);
      saveBlob(blob, `gradebook-${classroomId}.csv`);
    } catch {
      setError(t('classrooms.gradebook.downloadError'));
    } finally {
      setDownloading(false);
    }
  }

  if (loading) {
    return <Spinner />;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold text-slate-800 dark:text-slate-100">
          {t('classrooms.gradebook.title')}
        </h1>
        <div className="flex gap-2">
          <Link to={`/classrooms/${classroomId}`}>
            <Button variant="ghost">{t('common.back')}</Button>
          </Link>
          <Button onClick={() => void downloadCsv()} loading={downloading}>
            {t('classrooms.gradebook.download')}
          </Button>
        </div>
      </div>

      {error && <Alert tone="error">{error}</Alert>}

      {data && (
        <Card>
          <p className="mb-2 text-sm text-slate-600">
            {t('classrooms.gradebook.summary', {
              rate: Math.round(data.completion_rate * 100),
              overdue: data.overdue,
            })}
          </p>
          <Table caption={t('classrooms.gradebook.caption')}>
            <thead>
              <Tr>
                <Th>{t('classrooms.student')}</Th>
                {data.tasks.map((task) => (
                  <Th key={task.id}>{task.title}</Th>
                ))}
              </Tr>
            </thead>
            <tbody>
              {data.students.map((student) => (
                <Tr key={student.id}>
                  <Td>{student.username}</Td>
                  {data.tasks.map((task) => {
                    const cell = cells.get(`${student.id}:${task.id}`);
                    const status = cell?.status ?? 'not_started';
                    return (
                      <Td key={task.id}>
                        <span className="block">
                          {t(STATUS_KEYS[status] ?? STATUS_KEYS.not_started)}
                        </span>
                        <span className="text-xs text-slate-500">
                          {t('classrooms.gradebook.attempts', { count: cell?.attempts ?? 0 })}
                        </span>
                      </Td>
                    );
                  })}
                </Tr>
              ))}
            </tbody>
          </Table>
          {data.students.length === 0 && (
            <p className="text-sm text-slate-500">{t('classrooms.gradebook.empty')}</p>
          )}
        </Card>
      )}
    </div>
  );
}
