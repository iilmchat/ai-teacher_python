import { expect, test } from '@playwright/test';

import { registerStudent } from './helpers';

test.describe('Песочница кода', () => {
  test('выполняет безопасный код и показывает вывод', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/code');

    const editor = page.getByTestId('code-input');
    await editor.fill('print(sum(range(5)))');
    await page.getByRole('button', { name: 'Запустить' }).click();

    await expect(page.getByLabel('Результат')).toContainText('10', { timeout: 30_000 });
  });

  test('блокирует опасный импорт', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/code');

    const editor = page.getByTestId('code-input');
    await editor.fill('import os\nprint(os.getcwd())');
    await page.getByRole('button', { name: 'Запустить' }).click();

    await expect(page.getByRole('alert').first()).toContainText(/os|запрещ/i, {
      timeout: 30_000,
    });
  });

  test('сообщает об ошибке выполнения', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/code');

    const editor = page.getByTestId('code-input');
    await editor.fill('print(1 / 0)');
    await page.getByRole('button', { name: 'Запустить' }).click();

    await expect(page.getByRole('alert').first()).toContainText(/ZeroDivisionError/i, {
      timeout: 30_000,
    });
  });
});
