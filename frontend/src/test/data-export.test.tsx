import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { DataExportCard } from '@/components/profile/DataExportCard';
import { saveBlob } from '@/lib/download';
import { api } from '@/lib/api';
import { renderWithRouter } from '@/test/utils';

vi.mock('@/lib/download', () => ({
  saveBlob: vi.fn(),
}));

const SAVED = () => vi.mocked(saveBlob);

describe('выгрузка своих данных (S45-003)', () => {
  beforeEach(() => {
    SAVED().mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('кнопка скачивает JSON и сохраняет через saveBlob', async () => {
    const user = userEvent.setup();
    const blob = new Blob(['{"profile":{}}'], { type: 'application/json' });
    vi.spyOn(api, 'download').mockResolvedValue(blob);

    renderWithRouter(<DataExportCard />);
    await user.click(screen.getByRole('button', { name: 'Скачать мои данные' }));

    await waitFor(() => {
      expect(SAVED()).toHaveBeenCalledTimes(1);
    });
    expect(api.download).toHaveBeenCalledWith('/users/me/export');
    expect(SAVED().mock.calls[0][1]).toMatch(/^ai-teacher-export-\d{4}-\d{2}-\d{2}\.json$/);
    expect(screen.getByText('Файл скачан')).toBeInTheDocument();
  });

  it('ошибка сети показывает сообщение и не сохраняет файл', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'download').mockRejectedValue(new Error('boom'));

    renderWithRouter(<DataExportCard />);
    await user.click(screen.getByRole('button', { name: 'Скачать мои данные' }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Не удалось скачать данные',
      );
    });
    expect(SAVED()).not.toHaveBeenCalled();
  });
});
