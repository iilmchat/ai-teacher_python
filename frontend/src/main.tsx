import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import '@/i18n';
import { App } from '@/App';
import '@/index.css';

const container = document.getElementById('root');
if (!container) {
  throw new Error('Корневой элемент #root не найден');
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
