import i18n from '@/i18n';
interface SpinnerProps {
  label?: string;
}

export function Spinner({ label = i18n.t('common.loading') }: SpinnerProps) {
  return (
    <div className="flex items-center justify-center gap-3 py-8 text-sm text-slate-500">
      <span
        aria-hidden="true"
        className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent"
      />
      <span>{label}</span>
    </div>
  );
}
