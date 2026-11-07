import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { ApiError } from '@/lib/api';
import { useAuthStore } from '@/store/auth';

type Status = 'idle' | 'saved' | 'error';

interface PasswordForm {
  current: string;
  next: string;
  repeat: string;
}

/**
 * Надёжность пароля: 0–4 позиция порогов услуги (длина, регистры, цифры,
 * символы). Именуется «слабый» через «отличный» — S45-001.
 */
function passwordScore(value: string): number {
  if (!value) return -1;
  let score = 0;
  if (value.length >= 8) score += 1;
  if (value.length >= 12) score += 1;
  if (/[a-zа-я]/.test(value) && /[A-ZА-Я]/.test(value)) score += 1;
  if (/\d/.test(value) || /[^\w\s]/.test(value)) score += 1;
  return score;
}

const SCORE_I18N = [
  'short',
  'weak',
  'fair',
  'good',
  'strong',
] as const;

export function PasswordChangeCard() {
  const { t } = useTranslation();
  const changePassword = useAuthStore(
    (state) => state.changePassword,
  );
  const [form, setForm] = useState<PasswordForm>({
    current: '',
    next: '',
    repeat: '',
  });
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<Status>('idle');
  const [error, setError] = useState<string | null>(null);

  const score = passwordScore(form.next);
  const canSubmit =
    form.current.length > 0 &&
    form.next.length >= 8 &&
    form.next === form.repeat;

  function update(field: keyof PasswordForm, value: string) {
    setForm((previous) => ({ ...previous, [field]: value }));
    setStatus('idle');
    setError(null);
  }

  async function handleSubmit() {
    if (!canSubmit || saving) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await changePassword(form.current, form.next);
      setForm({ current: '', next: '', repeat: '' });
      setStatus('saved');
    } catch (err) {
      setStatus('error');
      setError(
        err instanceof ApiError ? err.message : t('profile.password.error'),
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <label htmlFor="password-current" className="text-sm text-slate-700">
        {t('profile.password.current')}
      </label>
      <input
        id="password-current"
        type="password"
        autoComplete="current-password"
        value={form.current}
        onChange={(event) => update('current', event.target.value)}
        className="rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm outline-none focus:border-indigo-500"
      />

      <label htmlFor="password-new" className="text-sm text-slate-700">
        {t('profile.password.new')}
      </label>
      <input
        id="password-new"
        type="password"
        autoComplete="new-password"
        value={form.next}
        onChange={(event) => update('next', event.target.value)}
        className="rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm outline-none focus:border-indigo-500"
      />
      {score >= 0 && (
        <p className="text-xs text-slate-500">
          {t(`profile.password.strength.${SCORE_I18N[score]}`)}
        </p>
      )}

      <label htmlFor="password-repeat" className="text-sm text-slate-700">
        {t('profile.password.repeat')}
      </label>
      <input
        id="password-repeat"
        type="password"
        autoComplete="new-password"
        value={form.repeat}
        onChange={(event) => update('repeat', event.target.value)}
        className="rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm outline-none focus:border-indigo-500"
      />
      {form.repeat.length > 0 && form.next !== form.repeat && (
        <p className="text-xs text-amber-700">
          {t('profile.password.mismatch')}
        </p>
      )}

      <Button
        onClick={() => void handleSubmit()}
        loading={saving}
        disabled={!canSubmit}
      >
        {t('profile.password.submit')}
      </Button>

      {status === 'saved' && (
        <Alert tone="success">{t('profile.password.saved')}</Alert>
      )}
      {status === 'error' && (
        <Alert tone="error">
          {error ?? t('profile.password.error')}
        </Alert>
      )}
    </div>
  );
}
