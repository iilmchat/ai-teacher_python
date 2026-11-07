import { expect, test } from '@playwright/test';

import { registerStudent } from './helpers';

test.describe('Спринт 45: аккаунт и безопасность', () => {
  test('смена пароля: выход и вход с новым паролем', async ({ page }) => {
    const username = await registerStudent(page);
    await page.goto('/profile');

    await page.getByLabel('Текущий пароль').fill('password123');
    await page.getByLabel('Новый пароль', { exact: true }).fill('newpassword456');
    await page.getByLabel('Повторите новый пароль').fill('newpassword456');
    await page.getByRole('button', { name: 'Сменить пароль' }).click();

    // Текущее устройство остаётся в системе после смены (S45-001).
    await expect(page.getByText(/Пароль изменён/)).toBeVisible();

    await page.getByRole('button', { name: 'Выйти', exact: true }).click();
    await expect(page).toHaveURL(/\/login/);

    await page.getByLabel('Имя пользователя').fill(username);
    await page.getByLabel('Пароль').fill('newpassword456');
    await page.getByRole('button', { name: 'Войти' }).click();

    // Новый пароль принят: вернулись в приложение под своим аккаунтом.
    await expect(page).not.toHaveURL(/\/login/);
    await expect(page.getByRole('link', { name: username })).toBeVisible();
  });

  test('переключатель языка в шапке меняет интерфейс', async ({ page }) => {
    await registerStudent(page);

    await page.getByLabel('Язык интерфейса').selectOption('English');

    // Переключились все строки, включая навигацию и подпись переключателя.
    await expect(page.getByLabel('Interface language')).toBeVisible();
    await expect(
      page.getByRole('navigation', { name: 'Main navigation' }),
    ).toBeVisible();

    // Настройка сохраняется в профиле — после перезагрузки язык тот же.
    await page.reload();
    await expect(page.getByLabel('Interface language')).toHaveValue('en');
  });

  test('активные сессии: текущая видна, «выйти везде» оставляет её', async ({
    page,
  }) => {
    const username = await registerStudent(page);
    await page.goto('/profile');

    await expect(
      page.getByRole('heading', { name: 'Активные сессии' }),
    ).toBeVisible();
    await expect(page.getByText('Это устройство')).toBeVisible();

    await page.getByRole('button', { name: 'Выйти на всех устройствах' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('button', { name: 'Выйти везде' }).click();

    await expect(page.getByText('Все другие сессии завершены')).toBeVisible();

    // Текущее устройство получило новую пару токенов и живо после перезагрузки.
    await page.reload();
    await expect(page.getByRole('link', { name: username })).toBeVisible();
    await expect(page.getByText('Это устройство')).toBeVisible();
  });

  test('выгрузка данных и сохранение настроек уведомлений', async ({ page }) => {
    await registerStudent(page);
    await page.goto('/profile');

    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Скачать мои данные' }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/^ai-teacher-export-.*\.json$/);
    await expect(page.getByText('Файл скачан')).toBeVisible();

    const emailToggle = page.getByLabel('Письма о новых назначениях');
    await expect(emailToggle).toBeChecked();
    // Чекбокс управляемый: состояние меняется после ответа сервера.
    await emailToggle.click();
    await expect(emailToggle).not.toBeChecked();
    await expect(page.getByText('Настройки сохранены')).toBeVisible();

    // Настройка хранится в профиле: после перезагрузки выключена.
    await page.reload();
    await expect(page.getByLabel('Письма о новых назначениях')).not.toBeChecked();
  });
});
