import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

export function NotFoundPage() {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col items-center gap-3 py-16 text-center">
      <p className="text-5xl font-bold text-indigo-600">404</p>
      <h1 className="text-xl font-semibold text-slate-900">{t('errors.notFoundTitle')}</h1>
      <p className="text-sm text-slate-600">{t('errors.notFoundText')}</p>
      <Link to="/" className="text-sm text-indigo-700 hover:underline">
        {t('errors.toHome')}
      </Link>
    </div>
  );
}
