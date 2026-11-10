import { expect, test } from '@playwright/test';

import { login, uniqueId } from './helpers';

const BASE_URL = `http://127.0.0.1:${process.env.E2E_FRONTEND_PORT ?? 3100}`;

async function accessToken(page: import('@playwright/test').Page): Promise<string> {
  const token = await page.evaluate(() => localStorage.getItem('ai-teacher.access'));
  expect(token).toBeTruthy();
  return token as string;
}

function taskPayload(title: string): Record<string, unknown> {
  return {
    title,
    description: 'E2E-задача для сценария админки: сумма двух чисел.',
    difficulty: 'easy',
    category: 'e2e',
    test_cases: [{ input: '2\n3\n', expected_output: '5' }],
    hints: ['Сложите числа'],
    solution_template: 'a = int(input())\nb = int(input())\nprint(a + b)\n',
  };
}

test.describe('Спринт 47: админ — аудит, выгрузка, модерация', () => {
  test('проходит путь аудит → выгрузка → модерация', async ({ page }) => {
    await login(page, 'e2e_admin');
    const token = await accessToken(page);
    const headers = { Authorization: `Bearer ${token}` };

    // Создание задачи админом пишет аудит task.created.
    const created = await page.request.post(`${BASE_URL}/api/v1/tasks`, {
      headers,
      data: taskPayload(`E2E аудит ${uniqueId()}`),
    });
    expect(created.ok()).toBeTruthy();

    // Импорт даёт задачу source=imported — она попадает в очередь модерации.
    const importedTitle = `E2E модерация ${uniqueId()}`;
    const imported = await page.request.post(`${BASE_URL}/api/v1/tasks/import`, {
      headers,
      data: { tasks: [taskPayload(importedTitle)] },
    });
    expect(imported.ok()).toBeTruthy();
    expect((await imported.json()).created).toBe(1);

    // 1) Аудит.
    await page.goto('/admin/audit');
    await expect(page.getByText('task.created').first()).toBeVisible();

    // 2) Выгрузка аналитики.
    await page.goto('/admin');
    await expect(
      page.getByRole('button', { name: 'Скачать аналитику' }),
    ).toBeVisible();
    await page.getByLabel('Набор').selectOption('users');
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Скачать аналитику' }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(
      /^analytics-users-\d{4}-\d{2}-\d{2}\.csv$/,
    );

    // 3) Модерация импортированной задачи.
    await page.goto('/admin/moderation');
    await page
      .getByRole('button', { name: `Открыть: ${importedTitle}` })
      .click();
    await expect(page.getByText(importedTitle).first()).toBeVisible();
    await page.getByRole('button', { name: 'Снять с публикации' }).click();
    await expect(page.getByText('Задача снята с публикации')).toBeVisible();
  });
});
