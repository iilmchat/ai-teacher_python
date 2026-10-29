import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { useAuthStore } from '@/store/auth';

export function RegisterPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const register = useAuthStore((state) => state.register);
  const loading = useAuthStore((state) => state.loading);
  const error = useAuthStore((state) => state.error);

  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await register(email, username, password);
      navigate('/', { replace: true });
    } catch {
      // Ошибка отображается из стора
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <Card title={t('auth.registerTitle')} description={t('auth.registerSubtitle')}>
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          {error && <Alert tone="error">{error}</Alert>}

          <Input
            label={t('auth.email')}
            name="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <Input
            label={t('auth.username')}
            name="username"
            autoComplete="username"
            minLength={3}
            required
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
          <Input
            label={t('auth.password')}
            name="password"
            type="password"
            autoComplete="new-password"
            minLength={8}
            required
            hint={t('auth.passwordHint')}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />

          <Button type="submit" loading={loading}>
            {t('auth.submitRegister')}
          </Button>

          <p className="text-center text-sm text-slate-600">
            {t('auth.hasAccount')}{' '}
            <Link to="/login" className="text-indigo-700 hover:underline">
              {t('auth.toLogin')}
            </Link>
          </p>
        </form>
      </Card>
    </div>
  );
}
