import { useTranslation } from 'react-i18next';

import type { SandboxLimits } from '@/types/api';

interface SandboxLimitsProps {
  limits: SandboxLimits | null;
  error?: boolean;
}

/**
 * Раскрывающийся блок «Ограничения песочницы» (S44-001).
 *
 * Данные приходят из `GET /code/limits`; пока ответа нет, показывается
 * загрузка, а при ошибке — короткая подсказка, а не пустой блок.
 */
export function SandboxLimits({ limits, error = false }: SandboxLimitsProps) {
  const { t } = useTranslation();

  return (
    <details className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm">
      <summary className="cursor-pointer font-medium text-slate-700">
        {t('code.limits')}
      </summary>

      {error && <p className="mt-2 text-rose-700">{t('code.limitsError')}</p>}

      {!error && !limits && (
        <p className="mt-2 text-slate-500">{t('common.loading')}</p>
      )}

      {limits && (
        <ul className="mt-2 flex flex-col gap-1 text-slate-600">
          <li>
            {t('code.limitsTimeout', { seconds: limits.timeout_seconds })}
          </li>
          <li>
            {t('code.limitsMemory', { megabytes: limits.memory_limit_mb })}
          </li>
          <li>
            {t('code.limitsCodeLength', { chars: limits.max_code_length })}
          </li>
          <li>
            {t('code.limitsOutput', { chars: limits.max_output_chars })}
          </li>
          <li>
            {t('code.limitsModules', {
              modules: limits.allowed_modules.join(', '),
            })}
          </li>
        </ul>
      )}
    </details>
  );
}
