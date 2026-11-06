/**
 * Личные сниппеты кода (S44-003).
 *
 * Сниппеты живут в `users.settings.snippets`: сервер хранит их как JSONB,
 * ограничивая количество и длины. Фронтенд разбирает значение защитно:
 * кэш профиля мог быть записан старой или повреждённой версией приложения.
 */

import type { CodeSnippet } from '@/types/api';

/** Максимум сниппетов — как на сервере */
export const MAX_CODE_SNIPPETS = 20;

/** Максимальная длина названия сниппета */
export const MAX_SNIPPET_NAME_LENGTH = 80;

/** Максимальная длина кода сниппета — как у запуска в песочнице */
export const MAX_SNIPPET_CODE_LENGTH = 20_000;

/** Название без лишних пробелов, не длиннее серверного лимита */
export function normalizeSnippetName(name: string): string {
  return name.trim().slice(0, MAX_SNIPPET_NAME_LENGTH);
}

function newSnippetId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `snippet-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

/** Создать новый сниппет из текущего кода */
export function newCodeSnippet(name: string, code: string): CodeSnippet {
  return {
    id: newSnippetId(),
    name: normalizeSnippetName(name),
    code,
  };
}

/**
 * Разобрать `users.settings.snippets` в валидный список.
 *
 * Некорректные записи отбрасываются, повторяющиеся id схлопываются,
 * лишние сниппеты сверх лимита не показываются. Так интерфейс остаётся
 * рабочим, даже если в настройках лежит что-то неожиданное.
 */
export function parseCodeSnippets(
  settings: Record<string, unknown> | null | undefined,
): CodeSnippet[] {
  const raw = settings?.snippets;
  if (!Array.isArray(raw)) {
    return [];
  }

  const snippets: CodeSnippet[] = [];
  const seen = new Set<string>();

  for (const item of raw) {
    if (typeof item !== 'object' || item === null) {
      continue;
    }
    const record = item as Record<string, unknown>;
    const { id, name, code } = record;

    if (
      typeof id !== 'string' ||
      id.length === 0 ||
      seen.has(id) ||
      typeof name !== 'string' ||
      name.trim().length === 0 ||
      typeof code !== 'string' ||
      code.length === 0 ||
      code.length > MAX_SNIPPET_CODE_LENGTH
    ) {
      continue;
    }

    seen.add(id);
    snippets.push({
      id,
      name: normalizeSnippetName(name),
      code,
    });

    if (snippets.length >= MAX_CODE_SNIPPETS) {
      break;
    }
  }

  return snippets;
}
