/**
 * ChatWelcome - Welcome screen when no session is selected
 */

import React from 'react';
import { useTranslation } from 'react-i18next';

export const ChatWelcome: React.FC = () => {
  const { t } = useTranslation('chat');

  return (
    <div data-name="chat-welcome-root" className="flex-1 flex items-center justify-center text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-900">
      <div data-name="chat-welcome-content" className="text-center">
        <p className="text-lg mb-4">{t('view.welcome')}</p>
        <p className="text-sm">{t('view.welcomeSubtitle')}</p>
      </div>
    </div>
  );
};
