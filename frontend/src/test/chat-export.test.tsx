import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { MessageInput } from '@/components/chat/MessageInput';
import { SessionList } from '@/components/chat/SessionList';
import {
  findTemplate,
  PROMPT_TEMPLATES,
  templatesForLevel,
} from '@/lib/promptTemplates';
import type { ChatSession } from '@/types/api';

function session(overrides: Partial<ChatSession> = {}): ChatSession {
  return {
    id: 's1',
    user_id: 'u1',
    level: 'basic',
    title: 'Первый вопрос',
    pinned: false,
    created_at: '2026-11-06T10:00:00',
    updated_at: '2026-11-06T10:00:00',
    ...overrides,
  };
}

describe('шаблоны промптов (S43-004)', () => {
  it('каждый шаблон имеет уникальный идентификатор и уровни', () => {
    const ids = PROMPT_TEMPLATES.map((template) => template.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(PROMPT_TEMPLATES.length).toBeGreaterThan(0);
    for (const template of PROMPT_TEMPLATES) {
      expect(template.levels.length).toBeGreaterThan(0);
    }
  });

  it('шаблоны подбираются по уровню помощи', () => {
    const basic = templatesForLevel('basic');
    const advanced = templatesForLevel('advanced');

    expect(basic.length).toBeGreaterThan(0);
    expect(basic.every((template) => template.levels.includes('basic'))).toBe(true);
    expect(advanced.every((template) => template.levels.includes('advanced'))).toBe(
      true,
    );
    // Базовому уровню не предлагаем шаблон с готовым решением
    expect(basic.map((template) => template.id)).not.toContain('full_solution');
  });

  it('шаблон находится по идентификатору', () => {
    expect(findTemplate('explain_code')?.id).toBe('explain_code');
    expect(findTemplate('unknown')).toBeUndefined();
    expect(findTemplate(null)).toBeUndefined();
  });
});

describe('MessageInput: шаблоны (S43-004)', () => {
  it('чип подставляет текст в поле ввода, но не отправляет его', async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    const onSelectTemplate = vi.fn();
    const templates = templatesForLevel('basic');

    render(
      <MessageInput
        onSend={onSend}
        templates={templates}
        onSelectTemplate={onSelectTemplate}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Объясни код' }));

    const input = screen.getByLabelText('Сообщение') as HTMLTextAreaElement;
    expect(input.value).toContain('Объясни');
    expect(onSelectTemplate).toHaveBeenCalledWith('explain_code');
    // Автоотправки нет — отправляет ученик
    expect(onSend).not.toHaveBeenCalled();
  });

  it('без шаблонов чипов нет', () => {
    render(<MessageInput onSend={vi.fn()} />);

    expect(screen.queryByRole('button', { name: 'Объясни код' })).not.toBeInTheDocument();
  });
});

describe('SessionList: выгрузка диалога (S43-004)', () => {
  it('кнопки выгрузки есть только у открытой сессии', async () => {
    const user = userEvent.setup();
    const onDownloadMarkdown = vi.fn();
    const onCopyMarkdown = vi.fn();

    render(
      <SessionList
        sessions={[session({ id: 's1' }), session({ id: 's2', title: 'Другой чат' })]}
        activeId="s1"
        onOpen={vi.fn()}
        onRename={vi.fn()}
        onTogglePin={vi.fn()}
        onDelete={vi.fn()}
        onDownloadMarkdown={onDownloadMarkdown}
        onCopyMarkdown={onCopyMarkdown}
      />,
    );

    await user.click(
      screen.getByRole('button', { name: 'Скачать .md: Первый вопрос' }),
    );
    expect(onDownloadMarkdown).toHaveBeenCalledWith('s1');

    await user.click(
      screen.getByRole('button', { name: 'Копировать: Первый вопрос' }),
    );
    expect(onCopyMarkdown).toHaveBeenCalledWith('s1');

    expect(
      screen.queryByRole('button', { name: 'Скачать .md: Другой чат' }),
    ).not.toBeInTheDocument();
  });
});
