import { expect, test, type Page } from '@playwright/test';

import { registerStudent } from './helpers';

/** Вход существующим пользователем без привязки к стартовому маршруту */
async function signIn(page: Page, username: string): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('Имя пользователя').fill(username);
  await page.getByLabel('Пароль').fill('password123');
  await page.getByRole('button', { name: 'Войти' }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

test.describe('Спринт 46: учитель и работы ученика', () => {
  test('учитель комментирует работу — ученик видит комментарий', async ({
    page,
  }) => {
    const username = await registerStudent(page);

    // Ученик вступает в класс учителя (класс готовит scripts/seed_e2e.py).
    await page.goto('/classrooms');
    await page.getByLabel('Код класса').fill('E2E46');
    await page.getByRole('button', { name: 'Вступить', exact: true }).click();
    await expect(page.getByText('Вы вступили в класс')).toBeVisible();

    // Ученик решает задачу — появляется попытка, которую увидит учитель.
    await page.goto('/tasks');
    const card = page
      .getByRole('listitem')
      .filter({ hasText: 'Сумма двух чисел' });
    await card.getByRole('link', { name: 'Открыть' }).click();
    await page
      .getByTestId('code-input')
      .fill('a = int(input())\nb = int(input())\nprint(a + b)');
    await page.getByRole('button', { name: 'Отправить решение' }).click();
    await expect(page.getByText(/Все тесты пройдены/)).toBeVisible({
      timeout: 60_000,
    });

    // Вход учителем.
    await page.getByRole('button', { name: 'Выйти', exact: true }).click();
    await expect(page).toHaveURL(/\/login/);
    await signIn(page, 'e2e_teacher');

    // Учитель находит ученика и открывает его работы.
    await page.goto('/teacher/students');
    await page.getByLabel('Имя или email').fill(username);
    await page.getByRole('button', { name: 'Прогресс', exact: true }).click();
    await page.getByRole('tab', { name: 'Работы' }).click();
    await page.getByRole('button', { name: 'Открыть' }).first().click();

    // Комментарий к попытке.
    await page
      .getByLabel('Что ученику стоит исправить или попробовать?')
      .fill('Молодец, но проверь ввод');
    await page.getByRole('button', { name: 'Отправить комментарий' }).click();
    await expect(page.getByText('Молодец, но проверь ввод')).toBeVisible();

    // Ученик видит комментарий в истории попыток.
    await page.getByRole('button', { name: 'Выйти', exact: true }).click();
    await signIn(page, username);
    await page.goto('/tasks');
    const sameTask = page
      .getByRole('listitem')
      .filter({ hasText: 'Сумма двух чисел' });
    await sameTask.getByRole('link', { name: 'Открыть' }).click();
    await expect(page.getByText('Молодец, но проверь ввод')).toBeVisible({
      timeout: 20_000,
    });
    await expect(
      page.getByText(/Комментарий учителя e2e_teacher/),
    ).toBeVisible();
  });
});
