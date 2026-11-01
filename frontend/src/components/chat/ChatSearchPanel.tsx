import { type FormEvent, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Button } from '@/components/ui/Button';
import { api } from '@/lib/api';
import type { ChatSearchItem, ChatSearchResponse } from '@/types/api';

interface ChatSearchPanelProps {
  /** Открыть найденную сессию (переход к диалогу) */
  onOpenSession: (sessionId: string) => void;
}

/** Подсветить вхождения запроса в тексте сообщения (S27-003) */
function highlight(text: string, query: string) {
  const needle = query.trim();
  if (!needle) return text;
  const lower = text.toLowerCase();
  const queryLower = needle.toLowerCase();
  const parts: React.ReactNode[] = [];
  let cursor = 0;
  let index = lower.indexOf(queryLower);
  while (index !== -1) {
    parts.push(text.slice(cursor, index));
    parts.push(
      <mark key={`${index}-${cursor}`} className="rounded bg-amber-200 px-0.5 text-slate-900">
        {text.slice(index, index + needle.length)}
      </mark>,
    );
    cursor = index + needle.length;
    index = lower.indexOf(queryLower, cursor);
  }
  parts.push(text.slice(cursor));
  return parts;
}

export function ChatSearchPanel({ onOpenSession }: ChatSearchPanelProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [items, setItems] = useState<ChatSearchItem[]>([]);
  const [mode, setMode] = useState<'semantic' | 'ilike' | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = query.trim();
    if (!text) return;
    setLoading(true);
    setError(null);
    try {
      const response = await api.get<ChatSearchResponse>(
        `/chat/search?q=${encodeURIComponent(text)}&limit=10`,
      );
      setItems(response.items);
      setMode(response.mode);
      setSearched(true);
    } catch {
      setError(t('chat.search.error'));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section aria-label={t('chat.search.title')} className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold text-slate-700">{t('chat.search.title')}</h2>
      <form onSubmit={handleSubmit} className="flex gap-1">
        <label htmlFor="chat-search-input" className="sr-only">
          {t('chat.search.label')}
        </label>
        <input
          id="chat-search-input"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t('chat.search.placeholder')}
          maxLength={200}
          className="min-w-0 flex-1 rounded-lg border border-slate-300 px-2 py-1.5 text-xs focus:border-indigo-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
        />
        <Button type="submit" loading={loading} className="px-2 py-1 text-xs">
          {t('chat.search.submit')}
        </Button>
      </form>

      <div aria-live="polite" className="text-xs text-slate-500">
        {loading && t('chat.search.loading')}
        {!loading && searched && items.length === 0 && t('chat.search.empty')}
        {!loading && items.length > 0 &&
          t('chat.search.found', {
            count: items.length,
            mode: mode === 'semantic' ? t('chat.search.modes.semantic') : t('chat.search.modes.ilike'),
          })}
        {error && (
          <span role="alert" className="text-rose-600">
            {error}
          </span>
        )}
      </div>

      {items.length > 0 && (
        <ul className="flex max-h-56 flex-col gap-1 overflow-y-auto">
          {items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => onOpenSession(item.session_id)}
                className="w-full rounded-lg border border-slate-200 px-2 py-1.5 text-left text-xs text-slate-700 hover:border-indigo-300 hover:bg-indigo-50 focus-visible:ring-2 focus-visible:ring-indigo-500"
              >
                <span className="block truncate font-medium text-slate-500">
                  {new Date(item.created_at).toLocaleString('ru-RU')}
                  {typeof item.score === 'number' && (
                    <span className="ml-1 text-[10px] text-slate-400">
                      {item.score.toFixed(2)}
                    </span>
                  )}
                </span>
                <span className="line-clamp-2">{highlight(item.content, query)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
