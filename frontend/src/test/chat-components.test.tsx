import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { LevelSelector } from '@/components/chat/LevelSelector';
import { MessageInput } from '@/components/chat/MessageInput';
import { MessageList } from '@/components/chat/MessageList';
import { RichText } from '@/components/chat/RichText';
import { splitCodeFences } from '@/lib/markdown';
import type { ChatMessage } from '@/types/api';

function message(role: ChatMessage['role'], content: string, id = 'm1'): ChatMessage {
  return {
    id,
    session_id: 's1',
    role,
    content,
    code_blocks: [],
    created_at: '2026-10-29T10:00:00',
  };
}

describe('splitCodeFences', () => {
  it('разделяет текст и блоки кода', () => {
    const segments = splitCodeFences('Текст\n```python\nprint(1)\n```\nХвост');

    expect(segments).toHaveLength(3);
    expect(segments[0]).toMatchObject({ kind: 'text' });
    expect(segments[1]).toMatchObject({ kind: 'code', value: 'print(1)' });
    expect(segments[2]).toMatchObject({ kind: 'text', value: '\nХвост' });
  });

  it('возвращает один текстовый сегмент без блоков', () => {
    expect(splitCodeFences('просто текст')).toEqual([
      { kind: 'text', value: 'просто текст' },
    ]);
  });

  it('поддерживает несколько блоков кода', () => {
    const segments = splitCodeFences('a\n```\nx=1\n```\nb\n```\ny=2\n```');

    expect(segments.filter((item) => item.kind === 'code')).toHaveLength(2);
  });
});

describe('RichText', () => {
  it('рендерит блок кода отдельным pre', () => {
    render(<RichText text={'Проверь код:\n```python\nprint(42)\n```'} />);

    expect(screen.getByText('print(42)')).toBeInTheDocument();
    expect(screen.getByText(/Проверь код/)).toBeInTheDocument();
  });
});

describe('MessageList', () => {
  it('показывает пустое состояние без сообщений', () => {
    render(<MessageList messages={[]} />);

    expect(screen.getByText(/Спросите что-нибудь/)).toBeInTheDocument();
  });

  it('рендерит сообщения ученика и ассистента', () => {
    render(
      <MessageList
        messages={[message('user', 'вопрос'), message('assistant', 'ответ', 'm2')]}
      />,
    );

    expect(screen.getByText('вопрос')).toBeInTheDocument();
    expect(screen.getByText('ответ')).toBeInTheDocument();
  });

  it('показывает черновик во время стриминга', () => {
    render(<MessageList messages={[]} draft="Печатаю…" streaming />);

    expect(screen.getByText('Печатаю…')).toBeInTheDocument();
  });

  it('помечает ответ с нарушением политики уровня', () => {
    render(
      <MessageList
        messages={[
          {
            ...message('assistant', 'Вот решение', 'm3'),
            warnings: ['basic_full_solution'],
          },
        ]}
      />,
    );

    expect(screen.getByRole('status')).toHaveTextContent(/готовое решение/);
  });
});

describe('MessageInput', () => {
  it('отправляет по Enter', async () => {
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} />);

    const input = screen.getByLabelText('Сообщение');
    await userEvent.type(input, 'привет{Enter}');

    expect(onSend).toHaveBeenCalledWith('привет');
    expect(input).toHaveValue('');
  });

  it('не отправляет пустое сообщение', async () => {
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} />);

    await userEvent.type(screen.getByLabelText('Сообщение'), '   {Enter}');

    expect(onSend).not.toHaveBeenCalled();
  });

  it('переносит строку по Shift+Enter, не отправляя', async () => {
    const onSend = vi.fn();
    render(<MessageInput onSend={onSend} />);

    await userEvent.type(screen.getByLabelText('Сообщение'), 'строка1{Shift>}{Enter}{/Shift}');

    expect(onSend).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Сообщение')).toHaveValue('строка1\n');
  });

  it('блокируется во время стриминга', () => {
    render(<MessageInput onSend={vi.fn()} disabled />);

    expect(screen.getByLabelText('Сообщение')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Отправить' })).toBeDisabled();
  });
});

describe('LevelSelector', () => {
  it('показывает три уровня и отмечает выбранный', () => {
    render(<LevelSelector value="intermediate" onChange={vi.fn()} />);

    expect(screen.getByRole('button', { name: 'Базовый' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
    expect(screen.getByRole('button', { name: 'Средний' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('button', { name: 'Продвинутый' })).toBeInTheDocument();
  });

  it('сообщает о выборе уровня', async () => {
    const onChange = vi.fn();
    render(<LevelSelector value="basic" onChange={onChange} />);

    await userEvent.click(screen.getByRole('button', { name: 'Продвинутый' }));

    expect(onChange).toHaveBeenCalledWith('advanced');
  });
});
