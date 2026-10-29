import { expect, test } from '@playwright/test';

import { login, registerStudent, uniqueId } from './helpers';

test.describe('Аутентификация', () => {
  test('регистрация, выход и повторный вход', async ({ page }) => {
    const username = await registerStudent(page);

    await page.getByRole('button', { name: 'Выйти' }).click();
    await expect(page).toHaveURL(/\/login/);

    await login(page, username);
    await expect(page.getByRole('link', { name: username })).toBeVisible();
  });

  test('защищённая страница перенаправляет на вход', async ({ page }) => {
    await page.goto('/tasks');
    await expect(page).toHaveURL(/\/login/);
  });

  test('ошибка при неверном пароле', async ({ page }) => {
    const username = uniqueId();
    await page.goto('/register');
    await page.getByLabel('Email').fill(`${username}@example.com`);
    await page.getByLabel('Имя пользователя').fill(username);
    await page.getByLabel('Пароль').fill('password123');
    await page.getByRole('button', { name: 'Создать аккаунт' }).click();
    await expect(page).toHaveURL(/\/$/);

    await page.getByRole('button', { name: 'Выйти' }).click();
    await page.getByLabel('Имя пользователя').fill(username);
    await page.getByLabel('Пароль').fill('wrong-password');
    await page.getByRole('button', { name: 'Войти' }).click();

    await expect(page.getByRole('alert')).toContainText(/Incorrect|неверн|Неверн/i);
  });

  test('ученик не попадает в админку', async ({ page }) => {
    await registerStudent(page);

    await page.goto('/admin');

    await expect(page.getByText(/Доступ только для администратора/)).toBeVisible();
  });
});
