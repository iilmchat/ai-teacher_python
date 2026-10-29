import { useTranslation } from 'react-i18next';

import { Card } from '@/components/ui/Card';

interface ComingSoonProps {
  titleKey: string;
}

/** Заглушка для разделов, которые появятся в следующих спринтах */
export function ComingSoonPage({ titleKey }: ComingSoonProps) {
  const { t } = useTranslation();

  return (
    <Card title={t(titleKey)}>
      <p className="text-sm text-slate-600">{t('common.comingSoon')}</p>
    </Card>
  );
}
