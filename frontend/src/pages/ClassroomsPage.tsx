import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { api } from '@/lib/api';
import { useAuthStore } from '@/store/auth';
import type { Classroom, ClassroomList } from '@/types/api';

export function ClassroomsPage() {
  const { t } = useTranslation();
  const user = useAuthStore((state) => state.user);
  const [classrooms, setClassrooms] = useState<Classroom[]>([]);
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const isTeacher = user?.role === 'teacher' || user?.role === 'admin';

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<ClassroomList>('/classrooms');
      setClassrooms(data.items);
    } catch {
      setError(t('classrooms.loadError'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function createClassroom() {
    if (name.trim().length < 3) {
      setError(t('classrooms.nameError'));
      return;
    }
    setError(null);
    try {
      await api.post<Classroom>('/classrooms', { name: name.trim() });
      setName('');
      setNotice(t('classrooms.created'));
      await load();
    } catch {
      setError(t('classrooms.createError'));
    }
  }

  async function joinClassroom() {
    if (!code.trim()) {
      return;
    }
    setError(null);
    try {
      await api.post<Classroom>('/classrooms/join', {
        join_code: code.trim(),
      });
      setCode('');
      setNotice(t('classrooms.joined'));
      await load();
    } catch {
      setError(t('classrooms.joinError'));
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">
          {t('classrooms.title')}
        </h1>
        <Button variant="secondary" onClick={() => void load()} loading={loading}>
          {t('teacher.refresh')}
        </Button>
      </div>

      {error && <Alert tone="error">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      {isTeacher && (
        <Card title={t('classrooms.createTitle')}>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={t('classrooms.namePlaceholder')}
              aria-label={t('classrooms.namePlaceholder')}
              className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
            <Button onClick={() => void createClassroom()}>
              {t('classrooms.create')}
            </Button>
          </div>
        </Card>
      )}

      <Card title={t('classrooms.joinTitle')}>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            value={code}
            onChange={(event) => setCode(event.target.value.toUpperCase())}
            placeholder={t('classrooms.codePlaceholder')}
            aria-label={t('classrooms.codePlaceholder')}
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm uppercase"
          />
          <Button variant="secondary" onClick={() => void joinClassroom()}>
            {t('classrooms.join')}
          </Button>
        </div>
      </Card>

      {loading && classrooms.length === 0 ? (
        <Spinner />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {classrooms.map((classroom) => (
            <Link
              key={classroom.id}
              to={`/classrooms/${classroom.id}`}
              className="rounded-xl border border-slate-200 bg-white p-4 hover:border-indigo-300"
            >
              <div className="flex items-center justify-between">
                <h2 className="font-semibold text-slate-800">{classroom.name}</h2>
                <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-xs text-slate-600">
                  {classroom.join_code}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {t('classrooms.members', { count: classroom.members_count })}
              </p>
            </Link>
          ))}
          {classrooms.length === 0 && !loading && (
            <p className="text-sm text-slate-500">{t('classrooms.empty')}</p>
          )}
        </div>
      )}
    </div>
  );
}
