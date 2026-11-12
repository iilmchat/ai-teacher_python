import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import '@/i18n';
import '@/store/theme';
import { initSentry } from '@/lib/sentry';
import { App } from '@/App';
import '@/index.css';

// S35-002: no-op без DSN; инициализация до рендера, чтобы поймать ранние ошибки.
initSentry();

const container = document.getElementById('root');
if (!container) {
  throw new Error('#root element not found');
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
