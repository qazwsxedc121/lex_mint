/**
 * LanguageSwitcher - Language toggle for the global sidebar
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { GlobeAltIcon, XMarkIcon } from '@heroicons/react/24/outline';

const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'zh-CN', label: '中文' },
];

interface LanguageSwitcherProps {
  collapsed: boolean;
}

export const LanguageSwitcher: React.FC<LanguageSwitcherProps> = ({ collapsed }) => {
  const { i18n, t } = useTranslation('common');
  const [open, setOpen] = React.useState(false);

  const currentLang = LANGUAGES.find((l) => l.code === i18n.language) || LANGUAGES[0];

  const handleChangeLanguage = (langCode: string) => {
    i18n.changeLanguage(langCode);
    setOpen(false);
  };

  return (
    <div data-name="language-switcher">
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={`w-full flex items-center justify-center px-3 py-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors ${
          collapsed ? '' : 'border border-gray-700'
        }`}
        title={currentLang.label}
        data-name="language-switcher-toggle"
      >
        <GlobeAltIcon className="h-5 w-5 flex-shrink-0" />
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" data-name="language-switcher-overlay">
          <div className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} />
          <div
            className="relative w-[360px] max-w-[95vw] rounded-xl border border-gray-200 bg-white shadow-xl dark:border-gray-700 dark:bg-gray-800"
            data-name="language-switcher-dialog"
          >
            <div className="flex items-center justify-between border-b border-gray-200 px-3 py-2 dark:border-gray-700">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Language</h3>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-300 dark:hover:bg-gray-700 dark:hover:text-gray-100"
                aria-label={t('close')}
              >
                <XMarkIcon className="h-4 w-4" />
              </button>
            </div>
            <div className="p-3 space-y-2">
              {LANGUAGES.map((lang) => {
                const isCurrent = lang.code === i18n.language;
                return (
                  <button
                    key={lang.code}
                    type="button"
                    onClick={() => handleChangeLanguage(lang.code)}
                    className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                      isCurrent
                        ? 'border-blue-500 bg-blue-50 text-blue-700 dark:border-blue-400 dark:bg-blue-500/20 dark:text-blue-200'
                        : 'border-gray-200 text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-700'
                    }`}
                    data-name={`language-switcher-option-${lang.code}`}
                  >
                    {lang.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
