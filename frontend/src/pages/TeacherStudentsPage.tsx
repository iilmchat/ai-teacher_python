import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { Table, Td, Th, Tr } from '@/components/ui/Table';
import { CodeEditor } from '@/components/code-editor/CodeEditor';
import { api } from '@/lib/api';
import type {
  TeacherAttempt,
  TeacherAttemptDetail,
  TeacherAttemptList,
  TeacherStudent,
  TeacherStudentDetail,
  TeacherStudentList,
} from '@/types/api';

type Tab = 'progress' | 'works';

export function TeacherStudentsPage() {
  const { t } = useTranslation();
  const [students, setStudents] = useState<TeacherStudent[]>([]);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<TeacherStudentDetail | null>(null);
  const [tab, setTab] = useState<Tab>('progress');
  const [attempts, setAttempts] = useState<TeacherAttempt[] | null>(null);
  const [attemptDetail, setAttemptDetail] = useState<TeacherAttemptDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [attemptsLoading, setAttemptsLoading] = useState(false);
  const [attemptDetailLoading, setAttemptDetailLoading] = useState(false);
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
    setTab('progress');
    setAttempts(null);
    setAttemptDetail(null);
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

  async function loadAttempts(studentId: string) {
    setAttemptsLoading(true);
    setError(null);
    try {
      const data = await api.get<TeacherAttemptList>(
        `/teacher/students/${studentId}/attempts`,
      );
      setAttempts(data.items);
    } catch {
      setError(t('teacher.works.loadError'));
    } finally {
      setAttemptsLoading(false);
    }
  }

  async function openWorks() {
    if (!selected) {
      return;
    }
    setTab('works');
    if (attempts === null) {
      await loadAttempts(selected.student.id);
    }
  }

  async function openAttempt(attempt: TeacherAttempt) {
    if (!selected) {
      return;
    }
    setAttemptDetailLoading(true);
    setError(null);
    try {
      const detail = await api.get<TeacherAttemptDetail>(
        `/teacher/students/${selected.student.id}/attempts/${attempt.id}`,
      );
      setAttemptDetail(detail);
    } catch {
      setError(t('teacher.works.detailError'));
    } finally {
      setAttemptDetailLoading(false);
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
          <div className="mb-3 flex gap-2" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'progress'}
              onClick={() => setTab('progress')}
              className={`rounded-lg px-3 py-1.5 text-sm ${
                tab === 'progress'
                  ? 'bg-indigo-600 text-white'
                  : 'border border-slate-300 text-slate-700 hover:bg-slate-50'
              }`}
            >
              {t('teacher.works.progressTab')}
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'works'}
              onClick={() => void openWorks()}
              className={`rounded-lg px-3 py-1.5 text-sm ${
                tab === 'works'
                  ? 'bg-indigo-600 text-white'
                  : 'border border-slate-300 text-slate-700 hover:bg-slate-50'
              }`}
            >
              {t('teacher.works.worksTab')}
            </button>
          </div>

          {tab === 'progress' && (
            <>
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
                      <Th className="py-2">{t('teacher.works.solution')}</Th>
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
                        <Td className="py-2">
                          {item.best_solution ? (
                            <details>
                              <summary className="cursor-pointer text-sm text-indigo-700">
                                {t('teacher.works.showSolution')}
                              </summary>
                              <pre className="mt-2 max-w-md overflow-x-auto rounded bg-slate-900 p-2 font-mono text-xs text-slate-100">
                                {item.best_solution}
                              </pre>
                            </details>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                </Table>
              </div>
            </>
          )}

          {tab === 'works' && (
            <div className="flex flex-col gap-3">
              {attemptsLoading && <Spinner />}
              {attempts && attempts.length === 0 && (
                <p className="text-sm text-slate-500">{t('teacher.works.empty')}</p>
              )}
              {attempts && attempts.length > 0 && (
                <div className="overflow-x-auto">
                  <Table>
                    <thead className="text-xs uppercase text-slate-500">
                      <Tr>
                        <Th className="py-2">{t('teacher.works.colDate')}</Th>
                        <Th className="py-2">{t('teacher.colTask')}</Th>
                        <Th className="py-2">{t('teacher.works.colResult')}</Th>
                        <Th className="py-2" />
                      </Tr>
                    </thead>
                    <tbody>
                      {attempts.map((attempt) => (
                        <Tr key={attempt.id} className="border-t border-slate-100">
                          <Td className="py-2 text-slate-600">
                            {new Date(attempt.created_at).toLocaleString('ru-RU')}
                          </Td>
                          <Td className="py-2 text-slate-800">{attempt.task_title}</Td>
                          <Td
                            className={`py-2 font-medium ${
                              attempt.passed ? 'text-emerald-700' : 'text-rose-700'
                            }`}
                          >
                            {attempt.passed
                              ? t('tasks.attemptPassed')
                              : t('tasks.attemptFailed')}{' '}
                            {t('tasks.attemptScore', {
                              passed: attempt.passed_count,
                              total: attempt.total_count,
                            })}
                          </Td>
                          <Td className="py-2">
                            <Button variant="ghost" onClick={() => void openAttempt(attempt)}>
                              {t('teacher.works.open')}
                            </Button>
                          </Td>
                        </Tr>
                      ))}
                    </tbody>
                  </Table>
                </div>
              )}
              {attemptDetailLoading && <Spinner />}
              {attemptDetail && (
                <div className="rounded-lg border border-slate-200 p-3">
                  <p className="mb-2 text-sm font-medium text-slate-800">
                    {attemptDetail.task_title} ·{' '}
                    {new Date(attemptDetail.created_at).toLocaleString('ru-RU')}
                  </p>
                  <CodeEditor
                    value={attemptDetail.code}
                    onChange={() => undefined}
                    readOnly
                    height="220px"
                  />
                  <Table className="mt-3 text-xs">
                    <thead className="text-slate-500">
                      <Tr>
                        <Th className="py-1">{t('tasks.case')}</Th>
                        <Th className="py-1">{t('teacher.works.colResult')}</Th>
                        <Th className="py-1">{t('teacher.works.expected')}</Th>
                        <Th className="py-1">{t('teacher.works.actual')}</Th>
                      </Tr>
                    </thead>
                    <tbody>
                      {attemptDetail.results.map((result) => (
                        <Tr key={result.index} className="border-t border-slate-100">
                          <Td className="py-1">{result.index + 1}</Td>
                          <Td
                            className={`py-1 ${
                              result.passed ? 'text-emerald-700' : 'text-rose-700'
                            }`}
                          >
                            {result.passed
                              ? t('tasks.casePassed')
                              : t('tasks.caseFailed')}
                          </Td>
                          <Td className="py-1 font-mono">{result.expected_output}</Td>
                          <Td className="py-1 font-mono">
                            {result.error ?? result.actual_output}
                          </Td>
                        </Tr>
                      ))}
                    </tbody>
                  </Table>
                </div>
              )}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
