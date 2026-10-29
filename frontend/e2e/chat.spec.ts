import { expect, test } from '@playwright/test';

import { registerStudent } from './helpers';

test.describe('Чат', () => {
  test('создаёт сессию и получает ответ ассистента', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/chat');

    await page.getByRole('button', { name: 'Новый чат' }).click();
    const input = page.getByLabel('Сообщение');
    await expect(input).toBeVisible({ timeout: 20_000 });

    await input.fill('Как работает цикл for?');
    await page.getByRole('button', { name: 'Отправить' }).click();

    // Провайдер echo отвечает на базовом уровне наводящим вопросом
    await expect(page.getByText(/Давай разберёмся вместе/)).toBeVisible({
      timeout: 30_000,
    });
    // Вопрос ученика есть в переписке (в ответе echo он тоже цитируется)
    await expect(
      page.getByText('Как работает цикл for?', { exact: true }),
    ).toBeVisible();
  });

  test('уровень выбирается при создании сессии', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/chat');

    await page.getByRole('button', { name: 'Продвинутый' }).click();
    await page.getByRole('button', { name: 'Новый чат' }).click();

    const input = page.getByLabel('Сообщение');
    await expect(input).toBeVisible({ timeout: 20_000 });
    await input.fill('Покажи решение');
    await page.getByRole('button', { name: 'Отправить' }).click();

    // На продвинутом уровне echo отдаёт разбор с блоком кода
    await expect(page.getByText(/Разбор вопроса/)).toBeVisible({ timeout: 30_000 });
  });
});
