import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { MessageFeedbackButtons } from '@/components/chat/MessageFeedback';
import type { MessageFeedback } from '@/types/api';

const FEEDBACK: MessageFeedback = {
  message_id: 'm1',
  value: -1,
  comment: 'Непонятно',
  created_at: '2026-11-06T10:00:00',
};

describe('MessageFeedback (S43-003)', () => {
  it('ставит положительную оценку', async () => {
    const user = userEvent.setup();
    const onRate = vi.fn();
    render(
      <MessageFeedbackButtons messageId="m1" onRate={onRate} onComment={vi.fn()} />,
    );

    await user.click(screen.getByRole('button', { name: 'Ответ помог' }));

    expect(onRate).toHaveBeenCalledWith('m1', 1);
  });

  it('открывает поле комментария после негативной оценки', async () => {
    const user = userEvent.setup();
    const onRate = vi.fn();
    render(
      <MessageFeedbackButtons messageId="m1" onRate={onRate} onComment={vi.fn()} />,
    );

    await user.click(screen.getByRole('button', { name: 'Ответ не помог' }));

    expect(onRate).toHaveBeenCalledWith('m1', -1);
    expect(screen.getByLabelText('Что было непонятно в ответе?')).toBeInTheDocument();
  });

  it('сохраняет комментарий', async () => {
    const user = userEvent.setup();
    const onComment = vi.fn();
    render(
      <MessageFeedbackButtons
        messageId="m1"
        feedback={FEEDBACK}
        onRate={vi.fn()}
        onComment={onComment}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Комментарий' }));
    const field = screen.getByLabelText('Что было непонятно в ответе?');
    await user.clear(field);
    await user.type(field, 'Слишком сложно');
    await user.click(screen.getByRole('button', { name: 'Сохранить' }));

    expect(onComment).toHaveBeenCalledWith('m1', 'Слишком сложно');
  });

  it('отмечает текущую оценку', () => {
    render(
      <MessageFeedbackButtons
        messageId="m1"
        feedback={FEEDBACK}
        onRate={vi.fn()}
        onComment={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: 'Ответ не помог' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('button', { name: 'Ответ помог' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('позволяет снять оценку', async () => {
    const user = userEvent.setup();
    const onClear = vi.fn();
    render(
      <MessageFeedbackButtons
        messageId="m1"
        feedback={FEEDBACK}
        onRate={vi.fn()}
        onComment={vi.fn()}
        onClear={onClear}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Снять оценку' }));

    expect(onClear).toHaveBeenCalledWith('m1');
  });
});
