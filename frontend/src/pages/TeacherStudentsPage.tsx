import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { Table, Td, Th, Tr } from '@/components/ui/Table';
import { api } from '@/lib/api';
import type {
  TeacherStudent,
  TeacherStudentDetail,
  TeacherStudentList,
} from '@/types/api';

export function TeacherStudentsPage() {
  const { t } = useTranslation();
  const [students, setStudents] = useState<TeacherStudent[]>([]);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<TeacherStudentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<TeacherStudentList>('/teacher/students');
      setStudents(data.items);
    } catch {
      setError(t('teacher.loadStudentsError'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function openStudent(student: TeacherStudent) {
    setDetailLoading(true);
    setError(null);
    try {
      const detail = await api.get<TeacherStudentDetail>(
        `/teacher/students/${student.id}/progress`,
      );
      setSelected(detail);
    } catch {
      setError(t('teacher.loadProgressError'));
    } finally {
      setDetailLoading(false);
    }
  }

  const visible = students.filter((student) => {
    const query = search.trim().toLowerCase();
    return (
      !query ||
      student.username.toLowerCase().includes(query) ||
      student.email.toLowerCase().includes(query)
    );
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">
          {t('teacher.studentsTitle')}
        </h1>
        <div className="flex gap-2">
          <Link
            to="/teacher/tasks"
            className="inline-flex items-center rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
          >
            {t('teacher.toTasks')}
          </Link>
          <Button variant="secondary" onClick={() => void load()} loading={loading}>
            {t('teacher.refresh')}
          </Button>
        </div>
      </div>

      {error && <Alert tone="error">{error}</Alert>}

      <Card title={t('teacher.studentsTable')}>
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={t('teacher.searchPlaceholder')}
          aria-label={t('teacher.searchPlaceholder')}
          className="mb-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
        {loading && students.length === 0 ? (
          <Spinner />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <thead className="text-xs uppercase text-slate-500">
                <Tr>
                  <Th className="py-2">{t('teacher.colStudent')}</Th>
                  <Th className="py-2">{t('teacher.colEmail')}</Th>
                  <Th className="py-2">{t('teacher.colLevel')}</Th>
                  <Th className="py-2">{t('teacher.colCompleted')}</Th>
                  <Th className="py-2">{t('teacher.colAttempts')}</Th>
                  <Th className="py-2">{t('teacher.colLastActive')}</Th>
                  <Th className="py-2" />
                </Tr>
              </thead>
              <tbody>
                {visible.map((student) => (
                  <Tr key={student.id} className="border-t border-slate-100">
                    <Td className="py-2 font-medium text-slate-800">
                      {student.username}
                    </Td>
                    <Td className="py-2 text-slate-600">{student.email}</Td>
                    <Td className="py-2 text-slate-600">
                      {t(`levels.${student.level}`)}
                    </Td>
                    <Td className="py-2 text-slate-600">{student.completed_tasks}</Td>
                    <Td className="py-2 text-slate-600">{student.attempts}</Td>
                    <Td className="py-2 text-slate-500">
                      {new Date(student.last_active).toLocaleDateString('ru-RU')}
                    </Td>
                    <Td className="py-2">
                      <Button variant="ghost" onClick={() => void openStudent(student)}>
                        {t('teacher.openProgress')}
                      </Button>
                    </Td>
                  </Tr>
                ))}
                {visible.length === 0 && !loading && (
                  <Tr>
                    <Td colSpan={7} className="py-4 text-center text-slate-500">
                      {t('teacher.noStudents')}
                    </Td>
                  </Tr>
                )}
              </tbody>
            </Table>
          </div>
        )}
      </Card>

      {selected && (
        <Card
          title={t('teacher.progressTitle', { name: selected.student.username })}
        >
          {detailLoading && <Spinner />}
          <div className="mb-3 grid gap-2 sm:grid-cols-3">
            <p className="rounded-lg bg-slate-50 p-2 text-sm">
              {t('teacher.completedOf', {
                completed: selected.completed,
                total: selected.total_tasks,
              })}
            </p>
            <p className="rounded-lg bg-slate-50 p-2 text-sm">
              {t('teacher.inProgress')}: {selected.in_progress}
            </p>
            <p className="rounded-lg bg-slate-50 p-2 text-sm">
              {t('teacher.completionRate')}: {selected.completion_rate}%
            </p>
          </div>
          <div className="overflow-x-auto">
            <Table>
              <thead className="text-xs uppercase text-slate-500">
                <Tr>
                  <Th className="py-2">{t('teacher.colTask')}</Th>
                  <Th className="py-2">{t('teacher.colStatus')}</Th>
                  <Th className="py-2">{t('teacher.colAttempts')}</Th>
                </Tr>
              </thead>
              <tbody>
                {selected.items.map((item) => (
                  <Tr key={item.task_id} className="border-t border-slate-100">
                    <Td className="py-2 text-slate-800">{item.title}</Td>
                    <Td className="py-2 text-slate-600">
                      {t(`tasks.status.${item.status}`)}
                    </Td>
                    <Td className="py-2 text-slate-600">{item.attempts}</Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </div>
        </Card>
      )}
    </div>
  );
}
