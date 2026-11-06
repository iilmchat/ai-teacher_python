import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '@/i18n';
import { CodeBlock } from '@/components/chat/CodeBlock';
import { api } from '@/lib/api';
import {
  buildCodeAttachment,
  putIncomingCode,
  readCodeDraft,
  takeIncomingCode,
  writeCodeDraft,
} from '@/lib/codeTransfer';
import { ChatPage } from '@/pages/ChatPage';
import { CodePage } from '@/pages/CodePage';

const navigateMock = vi.fn();

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => navigateMock };
});

describe('передача кода (S43-005)', () => {
  beforeEach(() => {
    navigateMock.mockClear();
    localStorage.clear();
  });

  it('код из чата доживает до песочницы и забирается один раз', () => {
    putIncomingCode('print(1)');

    expect(readCodeDraft()).toBeNull();
    expect(takeIncomingCode()).toBe('print(1)');
    expect(takeIncomingCode()).toBeNull();
  });

  it('черновик песочницы сохраняется', () => {
    writeCodeDraft('x = 1');

    expect(readCodeDraft()).toBe('x = 1');
  });

  it('код-вложение оформляется блоком кода', () => {
    const text = buildCodeAttachment('print(1)', 'Вот мой код:');

    expect(text).toContain('```python');
    expect(text).toContain('print(1)');
  });
});

describe('CodeBlock: кнопка «В песочницу» (S43-005)', () => {
  it('передаёт код в песочницу', async () => {
    const user = userEvent.setup();
    const onSendToSandbox = vi.fn();

    render(<CodeBlock code="print(1)" onSendToSandbox={onSendToSandbox} />);

    await user.click(screen.getByRole('button', { name: 'В песочницу' }));

    expect(onSendToSandbox).toHaveBeenCalledWith('print(1)');
  });

  it('без обработчика кнопки нет', () => {
    render(<CodeBlock code="print(1)" />);

    expect(screen.queryByRole('button', { name: 'В песочницу' })).not.toBeInTheDocument();
  });
});

describe('CodePage: приём кода из чата (S43-005)', () => {
  it('код без черновика подставляется сразу', async () => {
    putIncomingCode('print(1)');

    render(
      <MemoryRouter>
        <CodePage />
      </MemoryRouter>,
    );

    expect(await screen.findByTestId('monaco-mock')).toHaveValue('print(1)');
    expect(screen.queryByText(/Заменить текущий/)).not.toBeInTheDocument();
  });

  it('чужой черновик не перезаписывается без подтверждения', async () => {
    const user = userEvent.setup();
    writeCodeDraft('старый код');
    putIncomingCode('новый код');

    render(
      <MemoryRouter>
        <CodePage />
      </MemoryRouter>,
    );

    // Спрашиваем и показываем старый код
    expect(await screen.findByText(/В песочницу пришёл другой код/)).toBeInTheDocument();
    expect(screen.getByTestId('monaco-mock')).toHaveValue('старый код');

    await user.click(screen.getByRole('button', { name: 'Заменить' }));

    expect(screen.getByTestId('monaco-mock')).toHaveValue('новый код');
    expect(readCodeDraft()).toBe('новый код');
  });

  it('отказ от замены оставляет черновик на месте', async () => {
    const user = userEvent.setup();
    writeCodeDraft('старый код');
    putIncomingCode('новый код');

    render(
      <MemoryRouter>
        <CodePage />
      </MemoryRouter>,
    );

    await screen.findByText(/В песочницу пришёл другой код/);
    await user.click(screen.getByRole('button', { name: 'Оставить текущий' }));

    expect(screen.getByTestId('monaco-mock')).toHaveValue('старый код');
    expect(readCodeDraft()).toBe('старый код');
  });

  it('кнопка «Спросить ассистента» уводит в чат с кодом', async () => {
    const user = userEvent.setup();
    writeCodeDraft('print(1)');

    render(
      <MemoryRouter>
        <CodePage />
      </MemoryRouter>,
    );

    await user.click(screen.getByRole('button', { name: 'Спросить ассистента' }));

    expect(navigateMock).toHaveBeenCalledWith('/chat', { state: { code: 'print(1)' } });
  });
});

describe('ChatPage: код из песочницы (S43-005)', () => {
  it('код попадает в поле ввода и не отправляется сам', async () => {
    const session = {
      id: 's1',
      user_id: 'u1',
      level: 'basic',
      title: null,
      pinned: false,
      created_at: '2026-11-06T10:00:00',
      updated_at: '2026-11-06T10:00:00',
      messages: [],
    };
    const post = vi.spyOn(api, 'post').mockResolvedValue(session);
    vi.spyOn(api, 'get').mockImplementation(async (path: string) =>
      path === '/chat/sessions' ? [] : session,
    );

    render(
      <MemoryRouter initialEntries={[{ pathname: '/chat', state: { code: 'print(1)' } }]}>
        <ChatPage />
      </MemoryRouter>,
    );

    const input = await screen.findByLabelText('Сообщение');
    await waitFor(() => {
      expect((input as HTMLTextAreaElement).value).toContain('print(1)');
    });
    // Автоотправки нет — сообщение ждёт ученика
    const sent = post.mock.calls.some(([path]) => String(path).includes('/messages'));
    expect(sent).toBe(false);
  });
});
