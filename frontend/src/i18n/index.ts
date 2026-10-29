import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import en from '@/i18n/locales/en.json';
import ru from '@/i18n/locales/ru.json';

const STORAGE_KEY = 'ai-teacher.language';
const savedLanguage = localStorage.getItem(STORAGE_KEY);

void i18n.use(initReactI18next).init({
  resources: {
    ru: { translation: ru },
    en: { translation: en },
  },
  lng: savedLanguage ?? 'ru',
  fallbackLng: 'ru',
  interpolation: { escapeValue: false },
});

i18n.on('languageChanged', (language) => {
  localStorage.setItem(STORAGE_KEY, language);
});

export default i18n;
