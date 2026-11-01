import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { Table, Td, Th, Tr } from '@/components/ui/Table';
import { api } from '@/lib/api';
import { saveBlob } from '@/lib/download';
import { useAuthStore } from '@/store/auth';
import type {
  Assignment,
  AssignmentList,
  ClassProgress,
  ClassroomDetail,
  TeacherTaskItem,
  TeacherTaskList,
} from '@/types/api';

export function ClassroomDetailPage() {
  const { t } = useTranslation();
  const { classroomId = '' } = useParams();
  const user = useAuthStore((state) => state.user);
  const [classroom, setClassroom] = useState<ClassroomDetail | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [tasks, setTasks] = useState<TeacherTaskItem[]>([]);
  const [progress, setProgress] = useState<ClassProgress | null>(null);
  const [taskId, setTaskId] = useState('');
  const [selectedTaskIds, setSelectedTaskIds] = useState<string[]>([]);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [dueAt, setDueAt] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const isOwner = Boolean(classroom && user && classroom.owner_id === user.id);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [detail, assignmentData] = await Promise.all([
        api.get<ClassroomDetail>(`/classrooms/${classroomId}`),
        api.get<AssignmentList>(`/classrooms/${classroomId}/assignments`),
      ]);
      setClassroom(detail);
      setAssignments(assignmentData.items);
      if (detail.owner_id === user?.id) {
        const [taskData, progressData] = await Promise.all([
          api.get<TeacherTaskList>('/teacher/tasks'),
          api.get<ClassProgress>(`/classrooms/${classroomId}/progress`),
        ]);
        setTasks(taskData.items.filter((item) => item.is_active));
        setProgress(progressData);
      }
    } catch {
      setError(t('classrooms.detailError'));
    } finally {
      setLoading(false);
    }
  }, [classroomId, t, user?.id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function bulkAssign() {
    if (selectedTaskIds.length === 0) {
      return;
    }
    setBulkBusy(true);
    setError(null);
    try {
      const result = await api.post<{ created: string[]; skipped: string[]; unknown: string[] }>(
        `/classrooms/${classroomId}/assignments/bulk`,
        {
          task_ids: selectedTaskIds,
          due_at: dueAt ? new Date(dueAt).toISOString() : null,
        },
      );
      setNotice(
        t('classrooms.bulkAssigned', {
          created: result.created.length,
          skipped: result.skipped.length + result.unknown.length,
        }),
      );
      setSelectedTaskIds([]);
      await load();
    } catch {
      setError(t('classrooms.bulkError'));
    } finally {
      setBulkBusy(false);
    }
  }

  async function downloadReport() {
    setDownloading(true);
    setError(null);
    try {
      const blob = await api.download(`/classrooms/${classroomId}/report`);
      saveBlob(blob, `classroom-${classroomId}-report.csv`);
    } catch {
      setError(t('classrooms.reportError'));
    } finally {
      setDownloading(false);
    }
  }

  async function addAssignment() {
    if (!taskId) {
      return;
    }
    setError(null);
    try {
      await api.post<Assignment>(`/classrooms/${classroomId}/assignments`, {
        task_id: taskId,
        due_at: dueAt ? new Date(dueAt).toISOString() : null,
      });
      setNotice(t('classrooms.assignmentAdded'));
      setTaskId('');
      setDueAt('');
      await load();
    } catch {
      setError(t('classrooms.assignmentError'));
    }
  }

  async function removeMember(userId: string) {
    setError(null);
    try {
      await api.delete(`/classrooms/${classroomId}/members/${userId}`);
      await load();
    } catch {
      setError(t('classrooms.removeError'));
    }
  }

  function cell(studentId: string, taskIdValue: string) {
    const found = progress?.cells.find(
      (item) => item.student_id === studentId && item.task_id === taskIdValue,
    );
    if (!found) {
      return '—';
    }
    if (found.status === 'completed') {
      return `✓ ${found.attempts}`;
    }
    if (found.status === 'in_progress') {
      return `… ${found.attempts}`;
    }
    return `— ${found.attempts}`;
  }

  if (loading && !classroom) {
    return <Spinner />;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/classrooms" className="text-xs text-indigo-700 hover:underline">
            ← {t('classrooms.title')}
          </Link>
          <h1 className="text-xl font-semibold text-slate-900">
            {classroom?.name}
          </h1>
        </div>
        {classroom && (
          <span className="rounded bg-slate-100 px-2 py-1 font-mono text-sm text-slate-700">
            {classroom.join_code}
          </span>
        )}
      </div>

      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      <Card title={t('classrooms.assignments')}>
        {isOwner && (
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Button onClick={() => void downloadReport()} loading={downloading}>
              {t('classrooms.report')}
            </Button>
            <Link to={`/classrooms/${classroomId}/gradebook`}>
              <Button variant="ghost">{t('classrooms.gradebookLink')}</Button>
            </Link>
          </div>
        )}
        {isOwner && (
          <div className="mb-3 flex flex-col gap-2 sm:flex-row">
            <select
              value={taskId}
              onChange={(event) => setTaskId(event.target.value)}
              aria-label={t('classrooms.selectTask')}
              className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">{t('classrooms.selectTask')}</option>
              {tasks.map((task) => (
                <option key={task.id} value={task.id}>
                  {task.title}
                </option>
              ))}
            </select>
            <input
              type="datetime-local"
              value={dueAt}
              onChange={(event) => setDueAt(event.target.value)}
              aria-label={t('classrooms.dueAt')}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
            <Button onClick={() => void addAssignment()} disabled={!taskId}>
              {t('classrooms.assign')}
            </Button>
          </div>
        )}
        {isOwner && (
          <div className="mb-3 flex flex-col gap-2">
            <label className="text-sm font-medium text-slate-700" htmlFor="bulk-tasks">
              {t('classrooms.bulk')}
            </label>
            <select
              id="bulk-tasks"
              multiple
              size={Math.min(4, Math.max(2, tasks.length))}
              value={selectedTaskIds}
              onChange={(event) =>
                setSelectedTaskIds(
                  Array.from(event.target.selectedOptions).map((option) => option.value),
                )
              }
              aria-describedby="bulk-hint"
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              {tasks.map((task) => (
                <option key={task.id} value={task.id}>
                  {task.title}
                </option>
              ))}
            </select>
            <div className="flex items-center gap-2">
              <Button
                onClick={() => void bulkAssign()}
                disabled={selectedTaskIds.length === 0}
                loading={bulkBusy}
              >
                {t('classrooms.assign')}
              </Button>
              <span id="bulk-hint" className="text-xs text-slate-500">
                {t('classrooms.bulkHint')}
              </span>
            </div>
          </div>
        )}
        <div className="overflow-x-auto">
          <Table>
            <thead className="text-xs uppercase text-slate-500">
              <Tr>
                <Th className="py-2">{t('teacher.colTask')}</Th>
                <Th className="py-2">{t('classrooms.dueAt')}</Th>
                <Th className="py-2">{t('classrooms.done')}</Th>
              </Tr>
            </thead>
            <tbody>
              {assignments.map((item) => (
                <Tr key={item.id} className="border-t border-slate-100">
                  <Td className="py-2 font-medium text-slate-800">{item.title}</Td>
                  <Td className="py-2 text-slate-600">
                    {item.due_at
                      ? new Date(item.due_at).toLocaleString('ru-RU')
                      : '—'}
                  </Td>
                  <Td className="py-2 text-slate-600">
                    {item.completed_count}/{item.total_members}
                  </Td>
                </Tr>
              ))}
              {assignments.length === 0 && (
                <Tr>
                  <Td colSpan={3} className="py-3 text-center text-slate-500">
                    {t('classrooms.noAssignments')}
                  </Td>
                </Tr>
              )}
            </tbody>
          </Table>
        </div>
      </Card>

      {isOwner && progress && (
        <Card title={t('classrooms.progress')}>
          <p className="mb-2 text-sm text-slate-600">
            {t('classrooms.completionRate')}: {progress.completion_rate}%
          </p>
          <div className="overflow-x-auto">
            <Table className="text-xs">
              <thead className="text-slate-500">
                <Tr>
                  <Th className="py-2">{t('classrooms.student')}</Th>
                  {progress.tasks.map((task) => (
                    <Th key={task.id} className="max-w-24 truncate py-2">
                      {task.title}
                    </Th>
                  ))}
                </Tr>
              </thead>
              <tbody>
                {progress.students.map((student) => (
                  <Tr key={student.id} className="border-t border-slate-100">
                    <Td className="py-2 font-medium text-slate-800">
                      {student.username}
                    </Td>
                    {progress.tasks.map((task) => (
                      <Td key={task.id} className="py-2 text-slate-600">
                        {cell(student.id, task.id)}
                      </Td>
                    ))}
                  </Tr>
                ))}
              </tbody>
            </Table>
          </div>
          {progress.problem_tasks.length > 0 && (
            <div className="mt-3 text-xs text-amber-700">
              {t('classrooms.problemTasks')}:{' '}
              {progress.problem_tasks.map((item) => item.title).join(', ')}
            </div>
          )}
        </Card>
      )}

      <Card title={t('classrooms.members')}>
        <ul className="flex flex-col divide-y divide-slate-100 text-sm">
          {classroom?.members.map((member) => (
            <li key={member.user_id} className="flex items-center justify-between py-2">
              <span>{member.username}</span>
              <span className="flex items-center gap-2">
                <span className="text-xs text-slate-500">
                  {t(`classrooms.roles.${member.role}`, { defaultValue: member.role })}
                </span>
                {isOwner && member.role !== 'owner' && (
                  <Button
                    variant="ghost"
                    onClick={() => void removeMember(member.user_id)}
                  >
                    {t('classrooms.remove')}
                  </Button>
                )}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
