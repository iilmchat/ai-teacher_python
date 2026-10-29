import { expect, type Page } from '@playwright/test';

/** Уникальный суффикс, чтобы прогоны не конфликтовали в переиспользуемой БД */
export function uniqueId(prefix = 'e2e'): string {
  return `${prefix}_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}

/** Регистрация нового ученика через интерфейс */
export async function registerStudent(page: Page): Promise<string> {
  const username = uniqueId();
  await page.goto('/register');
  await page.getByLabel('Email').fill(`${username}@example.com`);
  await page.getByLabel('Имя пользователя').fill(username);
  await page.getByLabel('Пароль').fill('password123');
  await page.getByRole('button', { name: 'Создать аккаунт' }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole('link', { name: username })).toBeVisible();
  return username;
}

/** Вход существующим пользователем */
export async function login(page: Page, username: string): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('Имя пользователя').fill(username);
  await page.getByLabel('Пароль').fill('password123');
  await page.getByRole('button', { name: 'Войти' }).click();
  await expect(page).toHaveURL(/\/$/);
}
