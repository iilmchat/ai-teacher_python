import { useTranslation } from 'react-i18next';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/Button';
import { useAuthStore } from '@/store/auth';

const NAV_ITEMS = [
  { to: '/', labelKey: 'nav.home' },
  { to: '/chat', labelKey: 'nav.chat' },
  { to: '/tasks', labelKey: 'nav.tasks' },
  { to: '/code', labelKey: 'nav.code' },
] as const;

export function AppLayout() {
  const { t } = useTranslation();
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate('/login');
  }

  return (
    <div className="flex min-h-full flex-col">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <Link to="/" className="text-base font-semibold text-indigo-700">
            AI Teacher
          </Link>

          <nav className="hidden items-center gap-1 sm:flex" aria-label={t('nav.main')}>
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 text-sm transition-colors ${
                    isActive
                      ? 'bg-indigo-50 text-indigo-700'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`
                }
              >
                {t(item.labelKey)}
              </NavLink>
            ))}
            {user && (
              <>
                <NavLink
                  to="/dashboard"
                  className={({ isActive }) =>
                    `rounded-lg px-3 py-1.5 text-sm transition-colors ${
                      isActive
                        ? 'bg-indigo-50 text-indigo-700'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`
                  }
                >
                  {t('nav.dashboard')}
                </NavLink>
                <NavLink
                  to="/classrooms"
                  className={({ isActive }) =>
                    `rounded-lg px-3 py-1.5 text-sm transition-colors ${
                      isActive
                        ? 'bg-indigo-50 text-indigo-700'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`
                  }
                >
                  {t('nav.classrooms')}
                </NavLink>
                <NavLink
                  to="/assignments"
                  className={({ isActive }) =>
                    `rounded-lg px-3 py-1.5 text-sm transition-colors ${
                      isActive
                        ? 'bg-indigo-50 text-indigo-700'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`
                  }
                >
                  {t('nav.assignments')}
                </NavLink>
              </>
            )}
            {(user?.role === 'teacher' || user?.role === 'admin') && (
              <NavLink
                to="/teacher/tasks"
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 text-sm transition-colors ${
                    isActive
                      ? 'bg-indigo-50 text-indigo-700'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`
                }
              >
                {t('nav.teacher')}
              </NavLink>
            )}
            {user?.role === 'admin' && (
              <NavLink
                to="/admin"
                className={({ isActive }) =>
                  `rounded-lg px-3 py-1.5 text-sm transition-colors ${
                    isActive
                      ? 'bg-indigo-50 text-indigo-700'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`
                }
              >
                {t('admin.title')}
              </NavLink>
            )}
          </nav>

          <div className="flex items-center gap-3">
            {user ? (
              <>
                <Link
                  to="/profile"
                  className="text-sm text-slate-700 hover:text-indigo-700"
                  title={t('nav.profile')}
                >
                  {user.username}
                </Link>
                <Button variant="ghost" onClick={handleLogout}>
                  {t('nav.logout')}
                </Button>
              </>
            ) : (
              <>
                <Link
                  to="/login"
                  className="text-sm text-slate-600 hover:text-indigo-700"
                >
                  {t('nav.login')}
                </Link>
                <Link
                  to="/register"
                  className="text-sm text-indigo-700 hover:underline"
                >
                  {t('nav.register')}
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6">
        <Outlet />
      </main>

      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-500">
        © 2026 RuChating (iilmchat)
      </footer>
    </div>
  );
}
