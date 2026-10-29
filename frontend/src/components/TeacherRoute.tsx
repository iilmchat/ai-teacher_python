import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { useAuthStore } from '@/store/auth';

interface TeacherRouteProps {
  children: ReactNode;
}

/** Доступ преподавателю и администратору (ProtectedRoute уже проверил вход) */
export function TeacherRoute({ children }: TeacherRouteProps) {
  const user = useAuthStore((state) => state.user);

  if (!user || (user.role !== 'teacher' && user.role !== 'admin')) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-center">
        <p className="text-4xl">🔒</p>
        <h1 className="text-lg font-semibold text-slate-900">
          Доступ только для преподавателя
        </h1>
        <Link to="/" className="text-sm text-indigo-700 hover:underline">
          На главную
        </Link>
      </div>
    );
  }

  return <>{children}</>;
}
