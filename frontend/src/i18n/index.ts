import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import enCommon from './locales/en/common.json';
import enChat from './locales/en/chat.json';
import enSettings from './locales/en/settings.json';
import enProjects from './locales/en/projects.json';
import enWorkflow from './locales/en/workflow.json';

import zhCNCommon from './locales/zh-CN/common.json';
import zhCNChat from './locales/zh-CN/chat.json';
import zhCNSettings from './locales/zh-CN/settings.json';
import zhCNProjects from './locales/zh-CN/projects.json';
import zhCNWorkflow from './locales/zh-CN/workflow.json';

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: {
        common: enCommon,
        chat: enChat,
        settings: enSettings,
        projects: enProjects,
        workflow: enWorkflow,
      },
      'zh-CN': {
        common: zhCNCommon,
        chat: zhCNChat,
        settings: zhCNSettings,
        projects: zhCNProjects,
        workflow: zhCNWorkflow,
      },
    },
    fallbackLng: 'en',
    defaultNS: 'common',
    ns: ['common', 'chat', 'settings', 'projects', 'workflow'],
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: 'app-language',
      caches: ['localStorage'],
    },
  });

export default i18n;
