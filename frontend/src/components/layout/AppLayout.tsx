import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/Button';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import { useAuthStore } from '@/store/auth';

const NAV_ITEMS = [
  { to: '/', labelKey: 'nav.home' },
  { to: '/chat', labelKey: 'nav.chat' },
  { to: '/tasks', labelKey: 'nav.tasks' },
  { to: '/code', labelKey: 'nav.code' },
] as const;

function navClass({ isActive }: { isActive: boolean }) {
  return `rounded-lg px-3 py-1.5 text-sm transition-colors ${
    isActive
      ? 'bg-indigo-50 text-indigo-700'
      : 'text-slate-600 hover:bg-slate-100'
  }`;
}

export function AppLayout() {
  const { t, i18n } = useTranslation();
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const savePreferences = useAuthStore((state) => state.savePreferences);
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const isStaff = user?.role === 'teacher' || user?.role === 'admin';
  const language = i18n.language === 'en' ? 'en' : 'ru';

  function handleLanguage(next: 'ru' | 'en') {
    // S45-004: язык меняется сразу; авторизованному — ещё и сохраняется
    if (user) {
      void savePreferences({ language: next });
    } else {
      void i18n.changeLanguage(next);
    }
  }

  function handleLogout() {
    logout();
    navigate('/login');
  }

  const links = (
    <>
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          className={navClass}
          onClick={() => setMenuOpen(false)}
        >
          {t(item.labelKey)}
        </NavLink>
      ))}
      {user && (
        <>
          <NavLink
            to="/dashboard"
            className={navClass}
            onClick={() => setMenuOpen(false)}
          >
            {t('nav.dashboard')}
          </NavLink>
          <NavLink
            to="/classrooms"
            className={navClass}
            onClick={() => setMenuOpen(false)}
          >
            {t('nav.classrooms')}
          </NavLink>
          <NavLink
            to="/assignments"
            className={navClass}
            onClick={() => setMenuOpen(false)}
          >
            {t('nav.assignments')}
          </NavLink>
        </>
      )}
      {isStaff && (
        <NavLink
          to="/teacher/tasks"
          className={navClass}
          onClick={() => setMenuOpen(false)}
        >
          {t('nav.teacher')}
        </NavLink>
      )}
      {user?.role === 'admin' && (
        <NavLink
          to="/admin"
          className={navClass}
          onClick={() => setMenuOpen(false)}
        >
          {t('admin.title')}
        </NavLink>
      )}
    </>
  );

  return (
    <div className="flex min-h-full flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:text-sm focus:text-indigo-700"
      >
        {t('a11y.skipToContent')}
      </a>
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-2 px-4 py-3">
          <Link to="/" className="text-base font-semibold text-indigo-700">
            AI Teacher
          </Link>

          <nav
            className="hidden items-center gap-1 sm:flex"
            aria-label={t('nav.main')}
          >
            {links}
          </nav>

          <div className="flex items-center gap-1 sm:gap-2">
            <select
              aria-label={t('language.label')}
              value={language}
              onChange={(event) =>
                handleLanguage(event.target.value === 'en' ? 'en' : 'ru')
              }
              className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm text-slate-700"
            >
              <option value="ru">{t('language.ru')}</option>
              <option value="en">{t('language.en')}</option>
            </select>
            <ThemeToggle />
            <button
              type="button"
              className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 sm:hidden"
              aria-label={t('nav.menu')}
              aria-expanded={menuOpen}
              aria-controls="mobile-nav"
              onClick={() => setMenuOpen((value) => !value)}
            >
              <span aria-hidden="true">{menuOpen ? '✕' : '☰'}</span>
            </button>
            {user ? (
              <>
                <Link
                  to="/profile"
                  className="hidden text-sm text-slate-700 hover:text-indigo-700 sm:inline"
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

        {menuOpen && (
          <nav
            id="mobile-nav"
            aria-label={t('nav.mobile')}
            className="flex flex-col gap-1 border-t border-slate-200 px-4 py-2 sm:hidden"
          >
            {links}
            {user && (
              <Link
                to="/profile"
                className="rounded-lg px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
                onClick={() => setMenuOpen(false)}
              >
                {t('nav.profile')}
              </Link>
            )}
          </nav>
        )}
      </header>

      <main
        id="main"
        tabIndex={-1}
        className="mx-auto w-full max-w-5xl flex-1 px-4 py-6"
      >
        <Outlet />
      </main>

      <footer className="border-t border-slate-200 bg-white py-4 text-center text-xs text-slate-500">
        © 2026 RuChating (iilmchat)
      </footer>
    </div>
  );
}
