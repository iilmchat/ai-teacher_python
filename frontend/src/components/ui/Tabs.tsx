import type { ReactNode } from 'react';

interface TabItem {
  id: string;
  label: string;
  disabled?: boolean;
}

interface TabsProps {
  items: TabItem[];
  value: string;
  onChange: (id: string) => void;
  label: string;
}

export function Tabs({ items, value, onChange, label }: TabsProps) {
  return (
    <div role="tablist" aria-label={label} className="flex gap-1 border-b border-slate-200">
      {items.map((item) => {
        const selected = item.id === value;
        return (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`tab-${item.id}`}
            aria-selected={selected}
            aria-controls={`panel-${item.id}`}
            disabled={item.disabled}
            onClick={() => onChange(item.id)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${
              selected
                ? 'border-indigo-600 font-medium text-indigo-700'
                : 'border-transparent text-slate-600 hover:text-slate-900'
            } disabled:cursor-not-allowed disabled:opacity-50`}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

interface TabPanelProps {
  id: string;
  active: boolean;
  children: ReactNode;
}

export function TabPanel({ id, active, children }: TabPanelProps) {
  if (!active) {
    return null;
  }
  return (
    <div role="tabpanel" id={`panel-${id}`} aria-labelledby={`tab-${id}`} className="pt-3">
      {children}
    </div>
  );
}
