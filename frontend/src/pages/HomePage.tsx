import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { api } from '@/lib/api';
import { useAuthStore } from '@/store/auth';
import type { LevelInfo, LevelsResponse } from '@/types/api';

export function HomePage() {
  const { t } = useTranslation();
  const user = useAuthStore((state) => state.user);
  const [levels, setLevels] = useState<LevelInfo[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    api
      .get<LevelsResponse>('/chat/levels')
      .then((data) => {
        if (!cancelled) {
          setLevels(data.levels);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError(t('home.levelsLoading'));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [t]);

  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-2xl bg-gradient-to-br from-indigo-600 to-violet-600 px-6 py-10 text-white">
        <h1 className="text-3xl font-bold">{t('home.title')}</h1>
        <p className="mt-3 max-w-2xl text-indigo-100">{t('home.subtitle')}</p>
        <div className="mt-6 flex flex-wrap gap-3">
          {user ? (
            <>
              <Link to="/chat">
                <Button variant="secondary">{t('home.ctaChat')}</Button>
              </Link>
              <Link to="/tasks">
                <Button variant="ghost" className="text-white hover:bg-white/10">
                  {t('home.ctaTasks')}
                </Button>
              </Link>
            </>
          ) : (
            <Link to="/register">
              <Button variant="secondary">{t('auth.submitRegister')}</Button>
            </Link>
          )}
        </div>
      </section>

      <Card title={t('home.levelsTitle')}>
        {error && <Alert tone="warning">{error}</Alert>}
        {!error && levels.length === 0 && (
          <p className="text-sm text-slate-500">{t('common.loading')}</p>
        )}
        <ul className="grid gap-4 sm:grid-cols-3">
          {levels.map((level) => (
            <li
              key={level.level}
              className="rounded-lg border border-slate-200 p-4"
            >
              <h3 className="font-semibold text-slate-900">{level.title}</h3>
              <p className="mt-1 text-sm text-slate-600">{level.description}</p>
              <p className="mt-3 text-xs text-slate-500">{level.audience}</p>
            </li>
          ))}
        </ul>
      </Card>

      <Card title={t('home.featuresTitle')}>
        <ul className="grid gap-3 text-sm text-slate-700 sm:grid-cols-3">
          <li className="rounded-lg bg-slate-50 p-3">{t('home.featureChat')}</li>
          <li className="rounded-lg bg-slate-50 p-3">{t('home.featureCode')}</li>
          <li className="rounded-lg bg-slate-50 p-3">{t('home.featureTasks')}</li>
        </ul>
      </Card>
    </div>
  );
}
