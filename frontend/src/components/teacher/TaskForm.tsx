import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';

import {
  EMPTY_TASK_FORM,
  type TaskCaseValues,
  type TaskFormValues,
} from '@/components/teacher/taskFormTypes';
import { Button } from '@/components/ui/Button';

interface TaskFormProps {
  initial?: TaskFormValues;
  submitting?: boolean;
  error?: string | null;
  onSubmit: (values: TaskFormValues) => void;
  onCancel: () => void;
}

export function TaskForm({
  initial = EMPTY_TASK_FORM,
  submitting = false,
  error = null,
  onSubmit,
  onCancel,
}: TaskFormProps) {
  const { t } = useTranslation();
  const [values, setValues] = useState<TaskFormValues>(initial);
  const [validation, setValidation] = useState<string | null>(null);

  function update<K extends keyof TaskFormValues>(key: K, value: TaskFormValues[K]) {
    setValues((current) => ({ ...current, [key]: value }));
  }

  function updateCase(index: number, patch: Partial<TaskCaseValues>) {
    setValues((current) => ({
      ...current,
      test_cases: current.test_cases.map((item, i) =>
        i === index ? { ...item, ...patch } : item,
      ),
    }));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (values.title.trim().length < 3) {
      setValidation(t('teacher.validationTitle'));
      return;
    }
    if (values.description.trim().length < 10) {
      setValidation(t('teacher.validationDescription'));
      return;
    }
    if (values.test_cases.length === 0) {
      setValidation(t('teacher.validationCases'));
      return;
    }
    setValidation(null);
    onSubmit(values);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3" data-testid="task-form">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm text-slate-700">
          {t('teacher.fieldTitle')}
          <input
            value={values.title}
            onChange={(event) => update('title', event.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-slate-700">
          {t('teacher.fieldCategory')}
          <input
            value={values.category}
            onChange={(event) => update('category', event.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
      </div>

      <label className="flex flex-col gap-1 text-sm text-slate-700">
        {t('teacher.fieldDescription')}
        <textarea
          value={values.description}
          onChange={(event) => update('description', event.target.value)}
          rows={3}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
      </label>

      <div className="grid gap-3 sm:grid-cols-3">
        <label className="flex flex-col gap-1 text-sm text-slate-700">
          {t('teacher.fieldDifficulty')}
          <select
            value={values.difficulty}
            onChange={(event) =>
              update('difficulty', event.target.value as TaskFormValues['difficulty'])
            }
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="easy">{t('tasks.difficulty.easy')}</option>
            <option value="medium">{t('tasks.difficulty.medium')}</option>
            <option value="hard">{t('tasks.difficulty.hard')}</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm text-slate-700">
          {t('teacher.fieldTags')}
          <input
            value={values.tags}
            onChange={(event) => update('tags', event.target.value)}
            placeholder="loops, math"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-slate-700">
          {t('teacher.fieldHints')}
          <textarea
            value={values.hints}
            onChange={(event) => update('hints', event.target.value)}
            rows={2}
            placeholder={t('teacher.hintsPlaceholder')}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
      </div>

      <label className="flex flex-col gap-1 text-sm text-slate-700">
        {t('teacher.fieldSolution')}
        <textarea
          value={values.solution_template}
          onChange={(event) => update('solution_template', event.target.value)}
          rows={3}
          className="rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm"
        />
      </label>

      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">
            {t('teacher.testCases')}
          </h3>
          <Button
            type="button"
            variant="secondary"
            onClick={() =>
              update('test_cases', [
                ...values.test_cases,
                { input: '', expected_output: '', description: '' },
              ])
            }
          >
            {t('teacher.addCase')}
          </Button>
        </div>

        {values.test_cases.map((item, index) => (
          <div key={index} className="grid gap-2 rounded-lg bg-slate-50 p-2 sm:grid-cols-3">
            <label className="flex flex-col gap-1 text-xs text-slate-600">
              {t('teacher.caseInput')}
              <textarea
                aria-label={`${t('teacher.caseInput')} ${index + 1}`}
                value={item.input}
                onChange={(event) => updateCase(index, { input: event.target.value })}
                rows={2}
                className="rounded border border-slate-300 px-2 py-1 font-mono text-xs"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-slate-600">
              {t('teacher.caseExpected')}
              <textarea
                aria-label={`${t('teacher.caseExpected')} ${index + 1}`}
                value={item.expected_output}
                onChange={(event) =>
                  updateCase(index, { expected_output: event.target.value })
                }
                rows={2}
                className="rounded border border-slate-300 px-2 py-1 font-mono text-xs"
              />
            </label>
            <div className="flex flex-col gap-1 text-xs text-slate-600">
              <label>
                {t('teacher.caseDescription')}
                <input
                  aria-label={`${t('teacher.caseDescription')} ${index + 1}`}
                  value={item.description}
                  onChange={(event) =>
                    updateCase(index, { description: event.target.value })
                  }
                  className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-xs"
                />
              </label>
              <Button
                type="button"
                variant="ghost"
                onClick={() =>
                  update(
                    'test_cases',
                    values.test_cases.filter((_, i) => i !== index),
                  )
                }
              >
                {t('teacher.removeCase')}
              </Button>
            </div>
          </div>
        ))}
      </div>

      {(validation || error) && (
        <p role="alert" className="text-sm text-rose-600">
          {validation ?? error}
        </p>
      )}

      <div className="flex gap-2">
        <Button type="submit" loading={submitting}>
          {t('teacher.save')}
        </Button>
        <Button type="button" variant="secondary" onClick={onCancel}>
          {t('common.close')}
        </Button>
      </div>
    </form>
  );
}
