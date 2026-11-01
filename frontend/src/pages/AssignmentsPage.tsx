import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { Alert } from '@/components/ui/Alert';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { Table, Td, Th, Tr } from '@/components/ui/Table';
import { api } from '@/lib/api';
import type { MyAssignmentList } from '@/types/api';

export function AssignmentsPage() {
  const { t } = useTranslation();
  const [items, setItems] = useState<MyAssignmentList['items']>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api
      .get<MyAssignmentList>('/me/assignments')
      .then((data) => {
        if (active) {
          setItems(data.items);
        }
      })
      .catch(() => {
        if (active) {
          setError(t('classrooms.assignmentsError'));
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [t]);

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold text-slate-900">
        {t('classrooms.myAssignments')}
      </h1>
      {error && <Alert tone="error">{error}</Alert>}
      {loading ? (
        <Spinner />
      ) : (
        <Card title={t('classrooms.assignments')}>
          <div className="overflow-x-auto">
            <Table>
              <thead className="text-xs uppercase text-slate-500">
                <Tr>
                  <Th className="py-2">{t('teacher.colTask')}</Th>
                  <Th className="py-2">{t('classrooms.class')}</Th>
                  <Th className="py-2">{t('classrooms.dueAt')}</Th>
                  <Th className="py-2">{t('teacher.colStatus')}</Th>
                </Tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <Tr key={item.id} className="border-t border-slate-100">
                    <Td className="py-2">
                      <Link
                        to={`/tasks/${item.task_id}`}
                        className="font-medium text-indigo-700 hover:underline"
                      >
                        {item.title}
                      </Link>
                    </Td>
                    <Td className="py-2 text-slate-600">{item.classroom_name}</Td>
                    <Td className="py-2 text-slate-600">
                      {item.due_at
                        ? new Date(item.due_at).toLocaleString('ru-RU')
                        : '—'}
                    </Td>
                    <Td className="py-2">
                      {item.overdue ? (
                        <span className="rounded bg-rose-100 px-2 py-0.5 text-xs text-rose-700">
                          {t('classrooms.overdue')}
                        </span>
                      ) : (
                        <span className="text-slate-600">
                          {t(`tasks.status.${item.status}`)}
                        </span>
                      )}
                    </Td>
                  </Tr>
                ))}
                {items.length === 0 && (
                  <Tr>
                    <Td colSpan={4} className="py-4 text-center text-slate-500">
                      {t('classrooms.noMyAssignments')}
                    </Td>
                  </Tr>
                )}
              </tbody>
            </Table>
          </div>
        </Card>
      )}
    </div>
  );
}
