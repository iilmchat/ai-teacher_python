import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { useAuthStore } from '@/store/auth';

interface AdminRouteProps {
  children: ReactNode;
}

/** Доступ только администратору (ProtectedRoute уже проверил авторизацию) */
export function AdminRoute({ children }: AdminRouteProps) {
  const user = useAuthStore((state) => state.user);

  if (!user || user.role !== 'admin') {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <p className="text-4xl">🔒</p>
        <h1 className="text-lg font-semibold text-slate-900">Доступ только для администратора</h1>
        <Link to="/" className="text-sm text-indigo-700 hover:underline">
          На главную
        </Link>
      </div>
    );
  }

  return <>{children}</>;
}
