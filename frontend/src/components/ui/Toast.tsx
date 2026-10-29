import type { ReactNode } from 'react';

type ToastTone = 'success' | 'error' | 'info';

const TONES: Record<ToastTone, string> = {
  success: 'border-emerald-300 bg-emerald-50 text-emerald-800',
  error: 'border-rose-300 bg-rose-50 text-rose-800',
  info: 'border-indigo-300 bg-indigo-50 text-indigo-800',
};

export interface ToastItem {
  id: string;
  message: string;
  tone?: ToastTone;
}

interface ToastProps {
  item: ToastItem;
  onClose: (id: string) => void;
  dismissLabel?: string;
}

export function Toast({ item, onClose, dismissLabel = 'Dismiss' }: ToastProps) {
  return (
    <div
      role="status"
      className={`pointer-events-auto flex items-start gap-3 rounded-lg border px-4 py-3 text-sm shadow ${TONES[item.tone ?? 'info']}`}
    >
      <span className="flex-1">{item.message}</span>
      <button
        type="button"
        onClick={() => onClose(item.id)}
        aria-label={dismissLabel}
        className="rounded p-0.5 opacity-70 hover:opacity-100"
      >
        ✕
      </button>
    </div>
  );
}

interface ToastStackProps {
  items: ToastItem[];
  onClose: (id: string) => void;
  children?: ReactNode;
  dismissLabel?: string;
}

export function ToastStack({ items, onClose, dismissLabel }: ToastStackProps) {
  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2"
    >
      {items.map((item) => (
        <Toast
          key={item.id}
          item={item}
          onClose={onClose}
          dismissLabel={dismissLabel}
        />
      ))}
    </div>
  );
}
