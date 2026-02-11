/**
 * LanguageSwitcher - Language toggle for the global sidebar
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { LanguageIcon } from '@heroicons/react/24/outline';

const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'zh-CN', label: '中文' },
];

interface LanguageSwitcherProps {
  collapsed: boolean;
}

export const LanguageSwitcher: React.FC<LanguageSwitcherProps> = ({ collapsed }) => {
  const { i18n } = useTranslation();

  const currentLang = LANGUAGES.find((l) => l.code === i18n.language) || LANGUAGES[0];

  const handleToggle = () => {
    const currentIndex = LANGUAGES.findIndex((l) => l.code === i18n.language);
    const nextIndex = (currentIndex + 1) % LANGUAGES.length;
    i18n.changeLanguage(LANGUAGES[nextIndex].code);
  };

  if (collapsed) {
    return (
      <button
        onClick={handleToggle}
        className="w-full flex items-center justify-center px-3 py-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
        title={currentLang.label}
      >
        <LanguageIcon className="h-5 w-5" />
      </button>
    );
  }

  return (
    <select
      value={i18n.language}
      onChange={(e) => i18n.changeLanguage(e.target.value)}
      className="w-full px-3 py-2 text-sm text-gray-300 bg-gray-800 border border-gray-700 rounded-lg hover:bg-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
    >
      {LANGUAGES.map((lang) => (
        <option key={lang.code} value={lang.code}>
          {lang.label}
        </option>
      ))}
    </select>
  );
};
