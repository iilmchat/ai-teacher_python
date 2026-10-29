interface SpinnerProps {
  label?: string;
}

export function Spinner({ label = 'Загрузка…' }: SpinnerProps) {
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
