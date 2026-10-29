import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { useAuthStore } from '@/store/auth';

interface LocationState {
  from?: string;
}

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const login = useAuthStore((state) => state.login);
  const loading = useAuthStore((state) => state.loading);
  const error = useAuthStore((state) => state.error);

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await login(username, password);
      const state = location.state as LocationState | null;
      navigate(state?.from ?? '/', { replace: true });
    } catch {
      // Ошибка уже сохранена в сторе и показывается в Alert
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <Card title={t('auth.loginTitle')} description={t('auth.loginSubtitle')}>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          {error && <Alert tone="error">{error}</Alert>}

          <Input
            label={t('auth.username')}
            name="username"
            autoComplete="username"
            required
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
          <Input
            label={t('auth.password')}
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />

          <Button type="submit" loading={loading}>
            {t('auth.submitLogin')}
          </Button>

          <p className="text-center text-sm text-slate-600">
            {t('auth.noAccount')}{' '}
            <Link to="/register" className="text-indigo-700 hover:underline">
              {t('auth.toRegister')}
            </Link>
          </p>
        </form>
      </Card>
    </div>
  );
}
