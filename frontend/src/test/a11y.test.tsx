import { screen } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { describe, expect, it } from 'vitest';

import '@/i18n';
import { LoginPage } from '@/pages/LoginPage';
import { RegisterPage } from '@/pages/RegisterPage';
import { renderWithRouter } from '@/test/utils';

// jsdom не умеет canvas/цвета: контраст проверяется вручную по чек-листу
const AXE_OPTIONS = { rules: { 'color-contrast': { enabled: false } } };

describe('Accessibility (axe)', () => {
  it('страница входа без нарушений', async () => {
    const { container } = renderWithRouter(<LoginPage />);

    expect(await axe(container, AXE_OPTIONS)).toHaveNoViolations();
    expect(screen.getByLabelText(/Имя пользователя|Username/)).toBeInTheDocument();
  });

  it('страница регистрации без нарушений', async () => {
    const { container } = renderWithRouter(<RegisterPage />);

    expect(await axe(container, AXE_OPTIONS)).toHaveNoViolations();
  });
});
