import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router-dom';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { AssignmentTemplates } from '@/components/teacher/AssignmentTemplates';
import { Table, Td, Th, Tr } from '@/components/ui/Table';
import { api } from '@/lib/api';
import { saveBlob } from '@/lib/download';
import { useAuthStore } from '@/store/auth';
import type {
  AnnouncementItem,
  AnnouncementList,
  Assignment,
  AssignmentAnalytics,
  AssignmentList,
  BulkMembersAddResult,
  BulkMembersRemoveResult,
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
  const [analytics, setAnalytics] = useState<AssignmentAnalytics | null>(null);
  const [analyticsId, setAnalyticsId] = useState('');
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [dueDrafts, setDueDrafts] = useState<Record<string, string>>({});
  const [bulkDueAt, setBulkDueAt] = useState('');
  const [selectedAssignmentIds, setSelectedAssignmentIds] = useState<string[]>([]);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [assignmentBusy, setAssignmentBusy] = useState(false);
  const [bulkUsernames, setBulkUsernames] = useState('');
  const [selectedMemberIds, setSelectedMemberIds] = useState<string[]>([]);
  const [membersBusy, setMembersBusy] = useState(false);
  const [membersReport, setMembersReport] = useState<{
    added: string[];
    skipped: string[];
    unknown: string[];
  } | null>(null);
  const [announcements, setAnnouncements] = useState<AnnouncementItem[]>([]);
  const [announcementTitle, setAnnouncementTitle] = useState('');
  const [announcementBody, setAnnouncementBody] = useState('');
  const [announcementBusy, setAnnouncementBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const isOwner = Boolean(classroom && user && classroom.owner_id === user.id);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [detail, assignmentData, announcementData] = await Promise.all([
        api.get<ClassroomDetail>(`/classrooms/${classroomId}`),
        api.get<AssignmentList>(`/classrooms/${classroomId}/assignments`),
        api.get<AnnouncementList>(
          `/classrooms/${classroomId}/announcements`,
        ),
      ]);
      setClassroom(detail);
      setAssignments(assignmentData.items);
      setAnnouncements(announcementData.items);
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

  function toLocalInput(value: string | null): string {
    if (!value) {
      return '';
    }
    const date = new Date(value);
    const offset = date.getTimezoneOffset();
    return new Date(date.getTime() - offset * 60_000)
      .toISOString()
      .slice(0, 16);
  }

  async function saveDue(item: Assignment) {
    const value = dueDrafts[item.id] ?? toLocalInput(item.due_at);
    setAssignmentBusy(true);
    setError(null);
    try {
      await api.patch<Assignment>(
        `/classrooms/${classroomId}/assignments/${item.id}`,
        { due_at: value ? new Date(value).toISOString() : null },
      );
      setNotice(t('classrooms.dueUpdated'));
      setDueDrafts((current) => {
        const next = { ...current };
        delete next[item.id];
        return next;
      });
      await load();
    } catch {
      setError(t('classrooms.dueUpdateError'));
    } finally {
      setAssignmentBusy(false);
    }
  }

  async function removeAssignment(item: Assignment) {
    setAssignmentBusy(true);
    setError(null);
    try {
      await api.delete(`/classrooms/${classroomId}/assignments/${item.id}`);
      setNotice(t('classrooms.assignmentRemoved'));
      setConfirmDeleteId(null);
      setSelectedAssignmentIds((current) =>
        current.filter((id) => id !== item.id),
      );
      await load();
    } catch {
      setError(t('classrooms.assignmentRemoveError'));
    } finally {
      setAssignmentBusy(false);
    }
  }

  async function bulkShiftDue() {
    if (!bulkDueAt || selectedAssignmentIds.length === 0) {
      return;
    }
    setAssignmentBusy(true);
    setError(null);
    try {
      const iso = new Date(bulkDueAt).toISOString();
      for (const id of selectedAssignmentIds) {
        await api.patch<Assignment>(
          `/classrooms/${classroomId}/assignments/${id}`,
          { due_at: iso },
        );
      }
      setNotice(
        t('classrooms.bulkShifted', { count: selectedAssignmentIds.length }),
      );
      setSelectedAssignmentIds([]);
      setBulkDueAt('');
      await load();
    } catch {
      setError(t('classrooms.dueUpdateError'));
    } finally {
      setAssignmentBusy(false);
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

  async function addMembersBulk() {
    const usernames = bulkUsernames
      .split(/[\s,;]+/)
      .map((name) => name.trim())
      .filter(Boolean);
    if (usernames.length === 0) {
      return;
    }
    setMembersBusy(true);
    setError(null);
    setMembersReport(null);
    try {
      const result = await api.post<BulkMembersAddResult>(
        `/classrooms/${classroomId}/members/bulk`,
        { usernames: usernames.slice(0, 100) },
      );
      setMembersReport({
        added: result.added,
        skipped: result.skipped,
        unknown: result.unknown,
      });
      setBulkUsernames('');
      await load();
    } catch {
      setError(t('classrooms.bulkMembersError'));
    } finally {
      setMembersBusy(false);
    }
  }

  async function removeMembersBulk() {
    if (selectedMemberIds.length === 0) {
      return;
    }
    setMembersBusy(true);
    setError(null);
    try {
      const result = await api.delete<BulkMembersRemoveResult>(
        `/classrooms/${classroomId}/members/bulk`,
        { user_ids: selectedMemberIds },
      );
      setNotice(
        t('classrooms.bulkRemovedNotice', { count: result.removed.length }),
      );
      setSelectedMemberIds([]);
      await load();
    } catch {
      setError(t('classrooms.bulkRemoveMembersError'));
    } finally {
      setMembersBusy(false);
    }
  }

  function toggleMember(userId: string, checked: boolean) {
    setSelectedMemberIds((current) =>
      checked ? [...current, userId] : current.filter((id) => id !== userId),
    );
  }

  async function publishAnnouncement() {
    if (!announcementTitle.trim() || !announcementBody.trim()) {
      return;
    }
    setAnnouncementBusy(true);
    setError(null);
    try {
      await api.post<AnnouncementItem>(
        `/classrooms/${classroomId}/announcements`,
        {
          title: announcementTitle.trim(),
          body: announcementBody.trim(),
        },
      );
      setNotice(t('classrooms.announcementPublished'));
      setAnnouncementTitle('');
      setAnnouncementBody('');
      await load();
    } catch {
      setError(t('classrooms.announcementPublishError'));
    } finally {
      setAnnouncementBusy(false);
    }
  }

  async function removeAnnouncement(item: AnnouncementItem) {
    setAnnouncementBusy(true);
    setError(null);
    try {
      await api.delete(
        `/classrooms/${classroomId}/announcements/${item.id}`,
      );
      setNotice(t('classrooms.announcementDeleted'));
      await load();
    } catch {
      setError(t('classrooms.announcementDeleteError'));
    } finally {
      setAnnouncementBusy(false);
    }
  }

  async function openAnalytics(item: Assignment) {
    setAnalyticsId(item.id);
    setAnalyticsLoading(true);
    setError(null);
    try {
      const data = await api.get<AssignmentAnalytics>(
        `/classrooms/${classroomId}/assignments/${item.id}/analytics`,
      );
      setAnalytics(data);
    } catch {
      setError(t('classrooms.analyticsError'));
    } finally {
      setAnalyticsLoading(false);
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
        {isOwner && (
          <AssignmentTemplates
            classroomId={classroomId}
            selectedTaskIds={selectedTaskIds}
            onApplied={() => void load()}
          />
        )}
        {isOwner && (
          <div className="mb-3 flex flex-wrap items-end gap-2 rounded-lg bg-slate-50 p-2">
            <span className="text-xs text-slate-600">
              {t('classrooms.selectedAssignments', {
                count: selectedAssignmentIds.length,
              })}
            </span>
            <input
              type="datetime-local"
              value={bulkDueAt}
              onChange={(event) => setBulkDueAt(event.target.value)}
              aria-label={t('classrooms.bulkDue')}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
            />
            <Button
              variant="secondary"
              onClick={() => void bulkShiftDue()}
              loading={assignmentBusy}
              disabled={
                selectedAssignmentIds.length === 0 || !bulkDueAt
              }
            >
              {t('classrooms.bulkShift')}
            </Button>
          </div>
        )}
        <div className="overflow-x-auto">
          <Table>
            <thead className="text-xs uppercase text-slate-500">
              <Tr>
                {isOwner && (
                  <Th className="py-2">
                    <input
                      type="checkbox"
                      aria-label={t('classrooms.selectAllAssignments')}
                      checked={
                        assignments.length > 0 &&
                        selectedAssignmentIds.length === assignments.length
                      }
                      onChange={(event) =>
                        setSelectedAssignmentIds(
                          event.target.checked
                            ? assignments.map((item) => item.id)
                            : [],
                        )
                      }
                    />
                  </Th>
                )}
                <Th className="py-2">{t('teacher.colTask')}</Th>
                <Th className="py-2">{t('classrooms.dueAt')}</Th>
                <Th className="py-2">{t('classrooms.done')}</Th>
                {isOwner && <Th className="py-2">{t('classrooms.actions')}</Th>}
              </Tr>
            </thead>
            <tbody>
              {assignments.map((item) => (
                <Tr key={item.id} className={`border-t border-slate-100 ${analyticsId === item.id ? 'bg-indigo-50' : ''}`}>
                  {isOwner && (
                    <Td className="py-2">
                      <input
                        type="checkbox"
                        aria-label={t('classrooms.selectAssignment', {
                          title: item.title,
                        })}
                        checked={selectedAssignmentIds.includes(item.id)}
                        onChange={(event) =>
                          setSelectedAssignmentIds((current) =>
                            event.target.checked
                              ? [...current, item.id]
                              : current.filter((id) => id !== item.id),
                          )
                        }
                      />
                    </Td>
                  )}
                  <Td className="py-2 font-medium text-slate-800">
                    {isOwner ? (
                      <button
                        type="button"
                        onClick={() => void openAnalytics(item)}
                        className="text-left text-indigo-700 hover:underline"
                      >
                        {item.title}
                      </button>
                    ) : (
                      item.title
                    )}
                  </Td>
                  <Td className="py-2 text-slate-600">
                    {item.due_at
                      ? new Date(item.due_at).toLocaleString('ru-RU')
                      : '—'}
                  </Td>
                  <Td className="py-2 text-slate-600">
                    {item.completed_count}/{item.total_members}
                  </Td>
                  {isOwner && (
                    <Td className="py-2">
                      <div className="flex flex-wrap items-center gap-1">
                        <input
                          type="datetime-local"
                          aria-label={t('classrooms.dueFor', {
                            title: item.title,
                          })}
                          value={
                            dueDrafts[item.id] ?? toLocalInput(item.due_at)
                          }
                          onChange={(event) =>
                            setDueDrafts((current) => ({
                              ...current,
                              [item.id]: event.target.value,
                            }))
                          }
                          className="rounded border border-slate-300 px-2 py-1 text-xs"
                        />
                        <Button
                          variant="ghost"
                          onClick={() => void saveDue(item)}
                          disabled={assignmentBusy}
                        >
                          {t('classrooms.saveDue')}
                        </Button>
                        {confirmDeleteId === item.id ? (
                          <>
                            <Button
                              variant="danger"
                              onClick={() => void removeAssignment(item)}
                              disabled={assignmentBusy}
                            >
                              {t('classrooms.confirmRemoveAssignment')}
                            </Button>
                            <Button
                              variant="ghost"
                              onClick={() => setConfirmDeleteId(null)}
                            >
                              {t('classrooms.cancel')}
                            </Button>
                          </>
                        ) : (
                          <Button
                            variant="ghost"
                            onClick={() => setConfirmDeleteId(item.id)}
                          >
                            {t('classrooms.removeAssignment')}
                          </Button>
                        )}
                      </div>
                    </Td>
                  )}
                </Tr>
              ))}
              {assignments.length === 0 && (
                <Tr>
                  <Td
                    colSpan={isOwner ? 5 : 3}
                    className="py-3 text-center text-slate-500"
                  >
                    {t('classrooms.noAssignments')}
                  </Td>
                </Tr>
              )}
            </tbody>
          </Table>
        </div>
      </Card>

      {isOwner && analytics && (
        <Card
          title={t('classrooms.analyticsTitle', {
            title: analytics.task_title,
          })}
        >
          {analyticsLoading && <Spinner />}
          <div className="mb-3 grid gap-2 text-sm sm:grid-cols-4">
            <p className="rounded-lg bg-emerald-50 p-2">
              {t('classrooms.analyticsCompleted')}: {analytics.completed}
            </p>
            <p className="rounded-lg bg-amber-50 p-2">
              {t('classrooms.analyticsInProgress')}: {analytics.in_progress}
            </p>
            <p className="rounded-lg bg-slate-50 p-2">
              {t('classrooms.analyticsNotStarted')}: {analytics.not_started}
            </p>
            <p className="rounded-lg bg-rose-50 p-2">
              {t('classrooms.analyticsOverdue')}: {analytics.overdue}
            </p>
          </div>
          <p className="mb-2 text-sm text-slate-600">
            {t('classrooms.analyticsAttempts')}: {analytics.attempts_total} ·{' '}
            {t('classrooms.analyticsDistribution')}:{' '}
            {analytics.attempts_distribution
              .map((bucket) =>
                t('classrooms.analyticsBucket', {
                  attempts: bucket.attempts,
                  students: bucket.students,
                }),
              )
              .join(', ')}
          </p>
          <p className="mb-3 rounded-lg bg-rose-50 p-2 text-sm text-rose-800">
            {t('classrooms.analyticsProblem', {
              threshold: analytics.problem_threshold,
            })}
            :{' '}
            {analytics.problem_students.length === 0
              ? t('classrooms.analyticsNoProblems')
              : analytics.problem_students
                  .map((item) => item.username)
                  .join(', ')}
          </p>
          <div className="overflow-x-auto">
            <Table className="text-xs">
              <thead className="text-slate-500">
                <Tr>
                  <Th className="py-2">{t('classrooms.student')}</Th>
                  <Th className="py-2">{t('classrooms.analyticsStatus')}</Th>
                  <Th className="py-2">{t('classrooms.analyticsAttemptsCol')}</Th>
                  <Th className="py-2">{t('classrooms.analyticsWorks')}</Th>
                </Tr>
              </thead>
              <tbody>
                {analytics.students.map((item) => (
                  <Tr key={item.student_id} className="border-t border-slate-100">
                    <Td className="py-1 font-medium text-slate-800">
                      {item.username}
                    </Td>
                    <Td
                      className={`py-1 ${
                        item.overdue ? 'text-rose-700' : 'text-slate-600'
                      }`}
                    >
                      {t(`tasks.status.${item.status}`)}
                      {item.overdue ? ` · ${t('classrooms.analyticsOverdue')}` : ''}
                    </Td>
                    <Td className="py-1 text-slate-600">{item.attempts}</Td>
                    <Td className="py-1">
                      <Link
                        to={`/teacher/students?student=${item.student_id}&tab=works`}
                        className="text-indigo-700 hover:underline"
                      >
                        {t('classrooms.analyticsOpenWorks')}
                      </Link>
                    </Td>
                  </Tr>
                ))}
                {analytics.students.length === 0 && (
                  <Tr>
                    <Td colSpan={4} className="py-3 text-center text-slate-500">
                      {t('classrooms.analyticsEmpty')}
                    </Td>
                  </Tr>
                )}
              </tbody>
            </Table>
          </div>
        </Card>
      )}

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

      <Card title={t('classrooms.announcements')}>
        {isOwner && (
          <div className="mb-3 flex flex-col gap-2 border-b border-slate-100 pb-3">
            <input
              value={announcementTitle}
              onChange={(event) => setAnnouncementTitle(event.target.value)}
              placeholder={t('classrooms.announcementTitlePlaceholder')}
              aria-label={t('classrooms.announcementTitlePlaceholder')}
              maxLength={200}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
            <textarea
              value={announcementBody}
              onChange={(event) => setAnnouncementBody(event.target.value)}
              placeholder={t('classrooms.announcementBodyPlaceholder')}
              aria-label={t('classrooms.announcementBodyPlaceholder')}
              maxLength={5000}
              rows={3}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
            <div>
              <Button
                onClick={() => void publishAnnouncement()}
                loading={announcementBusy}
                disabled={
                  !announcementTitle.trim() || !announcementBody.trim()
                }
              >
                {t('classrooms.publishAnnouncement')}
              </Button>
            </div>
          </div>
        )}
        <ul className="flex flex-col divide-y divide-slate-100 text-sm">
          {announcements.map((item) => (
            <li key={item.id} className="py-2">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="font-medium text-slate-800">{item.title}</p>
                  <p className="text-xs text-slate-500">
                    {t('classrooms.announcementBy', {
                      author: item.author_name,
                      date: new Date(item.created_at).toLocaleString('ru-RU'),
                    })}
                  </p>
                </div>
                {item.can_delete && (
                  <Button
                    variant="ghost"
                    onClick={() => void removeAnnouncement(item)}
                    disabled={announcementBusy}
                  >
                    {t('classrooms.announcementDelete')}
                  </Button>
                )}
              </div>
              <p className="mt-1 whitespace-pre-wrap text-slate-700">
                {item.body}
              </p>
            </li>
          ))}
          {announcements.length === 0 && (
            <li className="py-2 text-slate-500">
              {t('classrooms.announcementsEmpty')}
            </li>
          )}
        </ul>
      </Card>

      <Card title={t('classrooms.members')}>
        {isOwner && (
          <div className="mb-3 flex flex-col gap-2 border-b border-slate-100 pb-3">
            <label
              htmlFor="bulk-usernames"
              className="text-xs font-medium text-slate-700"
            >
              {t('classrooms.bulkAddLabel')}
            </label>
            <textarea
              id="bulk-usernames"
              value={bulkUsernames}
              onChange={(event) => setBulkUsernames(event.target.value)}
              placeholder={t('classrooms.bulkAddPlaceholder')}
              rows={3}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
            <div className="flex flex-wrap items-center gap-2">
              <Button
                onClick={() => void addMembersBulk()}
                loading={membersBusy}
                disabled={!bulkUsernames.trim()}
              >
                {t('classrooms.bulkAddSubmit')}
              </Button>
              <span className="text-xs text-slate-500">
                {t('classrooms.bulkAddHint')}
              </span>
            </div>
            {membersReport && (
              <div className="rounded-lg bg-slate-50 p-2 text-xs text-slate-700">
                <p>
                  {t('classrooms.bulkAdded', {
                    names:
                      membersReport.added.length > 0
                        ? membersReport.added.join(', ')
                        : t('classrooms.bulkNone'),
                  })}
                </p>
                <p>
                  {t('classrooms.bulkSkipped', {
                    names:
                      membersReport.skipped.length > 0
                        ? membersReport.skipped.join(', ')
                        : t('classrooms.bulkNone'),
                  })}
                </p>
                <p>
                  {t('classrooms.bulkUnknown', {
                    names:
                      membersReport.unknown.length > 0
                        ? membersReport.unknown.join(', ')
                        : t('classrooms.bulkNone'),
                  })}
                </p>
              </div>
            )}
            {selectedMemberIds.length > 0 && (
              <div className="flex flex-wrap items-center gap-2 rounded-lg bg-rose-50 p-2">
                <span className="text-xs text-rose-800">
                  {t('classrooms.selectedMembers', {
                    count: selectedMemberIds.length,
                  })}
                </span>
                <Button
                  variant="danger"
                  onClick={() => void removeMembersBulk()}
                  loading={membersBusy}
                >
                  {t('classrooms.bulkRemoveSubmit')}
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => setSelectedMemberIds([])}
                >
                  {t('classrooms.cancel')}
                </Button>
              </div>
            )}
          </div>
        )}
        <ul className="flex flex-col divide-y divide-slate-100 text-sm">
          {classroom?.members.map((member) => (
            <li key={member.user_id} className="flex items-center justify-between py-2">
              <span className="flex items-center gap-2">
                {isOwner && member.role !== 'owner' && (
                  <input
                    type="checkbox"
                    aria-label={t('classrooms.selectMember', {
                      name: member.username,
                    })}
                    checked={selectedMemberIds.includes(member.user_id)}
                    onChange={(event) =>
                      toggleMember(member.user_id, event.target.checked)
                    }
                  />
                )}
                <span>{member.username}</span>
              </span>
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
          {classroom?.members.length === 0 && (
            <li className="py-2 text-slate-500">
              {t('classrooms.noMembers')}
            </li>
          )}
        </ul>
      </Card>
    </div>
  );
}
