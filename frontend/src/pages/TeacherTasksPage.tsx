import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { TaskForm } from '@/components/teacher/TaskForm';
import {
  EMPTY_TASK_FORM,
  type TaskFormValues,
} from '@/components/teacher/taskFormTypes';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { Table, Td, Th, Tr } from '@/components/ui/Table';
import { ApiError, api } from '@/lib/api';
import type {
  TaskAdminDetail,
  TaskImportPreview,
  TaskImportReport,
  TeacherTaskItem,
  TeacherTaskList,
} from '@/types/api';

export function TeacherTasksPage() {
  const { t } = useTranslation();
  const [tasks, setTasks] = useState<TeacherTaskItem[]>([]);
  const [form, setForm] = useState<TaskFormValues | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<TaskImportPreview | null>(null);
  const [report, setReport] = useState<TaskImportReport | null>(null);
  const [importing, setImporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<TeacherTaskList>('/teacher/tasks');
      setTasks(data.items);
    } catch {
      setError(t('teacher.loadError'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function openEdit(id: string) {
    setError(null);
    try {
      const task = await api.get<TaskAdminDetail>(`/teacher/tasks/${id}`);
      setForm({
        id: task.id,
        title: task.title,
        description: task.description,
        difficulty: task.difficulty,
        category: task.category,
        tags: (task.tags ?? []).join(', '),
        hints: task.hints.join('\n'),
        solution_template: task.solution_template ?? '',
        test_cases: task.test_cases.map((item) => ({
          input: item.input,
          expected_output: item.expected_output,
          description: item.description ?? '',
        })),
      });
    } catch {
      setError(t('teacher.loadTaskError'));
    }
  }

  async function save(values: TaskFormValues) {
    setSaving(true);
    setError(null);
    const payload = {
      title: values.title.trim(),
      description: values.description.trim(),
      difficulty: values.difficulty,
      category: values.category.trim() || 'general',
      tags: values.tags
        .split(',')
        .map((tag) => tag.trim())
        .filter(Boolean),
      hints: values.hints
        .split('\n')
        .map((hint) => hint.trim())
        .filter(Boolean),
      solution_template: values.solution_template.trim() || null,
      test_cases: values.test_cases.map((item) => ({
        input: item.input,
        expected_output: item.expected_output,
        description: item.description.trim() || null,
      })),
    };
    try {
      if (values.id) {
        await api.patch<TaskAdminDetail>(`/tasks/${values.id}`, payload);
        setNotice(t('teacher.taskUpdated'));
      } else {
        await api.post<TaskAdminDetail>('/tasks', payload);
        setNotice(t('teacher.taskCreated'));
      }
      setForm(null);
      await load();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : t('teacher.saveError'));
    } finally {
      setSaving(false);
    }
  }

  async function deactivate(task: TeacherTaskItem) {
    setError(null);
    try {
      await api.delete(`/tasks/${task.id}`);
      setNotice(t('teacher.taskDeactivated'));
      await load();
    } catch {
      setError(t('teacher.deleteError'));
    }
  }

  async function chooseFile(selected: File | null) {
    setFile(selected);
    setPreview(null);
    setReport(null);
    if (!selected) {
      return;
    }
    try {
      const content = await selected.text();
      const result = await api.post<TaskImportPreview>('/tasks/import/preview', {
        content,
      });
      setPreview(result);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : t('teacher.importError'));
    }
  }

  async function confirmImport() {
    if (!file) {
      return;
    }
    setImporting(true);
    setError(null);
    try {
      const result = await api.postFile<TaskImportReport>('/tasks/import/file', file);
      setReport(result);
      setPreview(null);
      setFile(null);
      await load();
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : t('teacher.importError'));
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">{t('teacher.tasksTitle')}</h1>
        <div className="flex gap-2">
          <Link
            to="/teacher/students"
            className="inline-flex items-center rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
          >
            {t('teacher.toStudents')}
          </Link>
          <Button variant="secondary" onClick={() => void load()} loading={loading}>
            {t('teacher.refresh')}
          </Button>
          <Button onClick={() => setForm({ ...EMPTY_TASK_FORM })}>
            {t('teacher.newTask')}
          </Button>
        </div>
      </div>

      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      {form && (
        <Card title={form.id ? t('teacher.editTask') : t('teacher.newTask')}>
          <TaskForm
            key={form.id ?? 'new'}
            initial={form}
            submitting={saving}
            error={error}
            onSubmit={(values) => void save(values)}
            onCancel={() => setForm(null)}
          />
        </Card>
      )}

      <Card title={t('teacher.tasksTable')}>
        {loading && tasks.length === 0 ? (
          <Spinner />
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <thead className="text-xs uppercase text-slate-500">
                <Tr>
                  <Th className="py-2">{t('teacher.colTitle')}</Th>
                  <Th className="py-2">{t('teacher.colDifficulty')}</Th>
                  <Th className="py-2">{t('teacher.colCategory')}</Th>
                  <Th className="py-2">{t('teacher.colTests')}</Th>
                  <Th className="py-2">{t('teacher.colActive')}</Th>
                  <Th className="py-2">{t('teacher.colActions')}</Th>
                </Tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <Tr key={task.id} className="border-t border-slate-100">
                    <Td className="py-2 font-medium text-slate-800">
                      {task.title}
                      {task.tags.length > 0 && (
                        <span className="ml-2 text-xs text-slate-400">
                          {task.tags.join(', ')}
                        </span>
                      )}
                    </Td>
                    <Td className="py-2 text-slate-600">
                      {t(`tasks.difficulty.${task.difficulty}`)}
                    </Td>
                    <Td className="py-2 text-slate-600">{task.category}</Td>
                    <Td className="py-2 text-slate-600">{task.test_cases_count}</Td>
                    <Td className="py-2">
                      {task.is_active ? '✓' : '—'}
                    </Td>
                    <Td className="flex gap-1 py-2">
                      <Button variant="ghost" onClick={() => void openEdit(task.id)}>
                        {t('teacher.edit')}
                      </Button>
                      {task.is_active && (
                        <Button variant="ghost" onClick={() => void deactivate(task)}>
                          {t('teacher.deactivate')}
                        </Button>
                      )}
                    </Td>
                  </Tr>
                ))}
                {tasks.length === 0 && !loading && (
                  <Tr>
                    <Td colSpan={6} className="py-4 text-center text-slate-500">
                      {t('teacher.noTasks')}
                    </Td>
                  </Tr>
                )}
              </tbody>
            </Table>
          </div>
        )}
      </Card>

      <Card title={t('teacher.importTitle')}>
        <p className="mb-2 text-sm text-slate-600">{t('teacher.importHint')}</p>
        <input
          type="file"
          accept=".json,.yaml,.yml,application/json,text/yaml"
          aria-label={t('teacher.importFile')}
          onChange={(event) => void chooseFile(event.target.files?.[0] ?? null)}
          className="text-sm"
        />
        {preview && (
          <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm">
            <p>
              {t('teacher.previewSummary', {
                tasks: preview.tasks,
                errors: preview.errors.length,
              })}
            </p>
            {preview.errors.length > 0 && (
              <ul className="mt-2 list-disc pl-5 text-xs text-rose-600">
                {preview.errors.slice(0, 5).map((item) => (
                  <li key={item.index}>
                    #{item.index + 1} {item.title ?? ''}: {item.message}
                  </li>
                ))}
              </ul>
            )}
            <Button
              className="mt-3"
              loading={importing}
              disabled={preview.tasks === 0}
              onClick={() => void confirmImport()}
            >
              {t('teacher.confirmImport')}
            </Button>
          </div>
        )}
        {report && (
          <Alert tone="success">
            {t('teacher.importReport', {
              created: report.created,
              skipped: report.skipped,
              errors: report.errors.length,
            })}
          </Alert>
        )}
      </Card>
    </div>
  );
}
