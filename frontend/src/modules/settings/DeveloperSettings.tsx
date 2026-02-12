/**
 * Developer Settings - Enables developer tools
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { PageHeader } from './components/common';
import { useDeveloperMode } from '../../hooks/useDeveloperMode';

export const DeveloperSettings: React.FC = () => {
  const { enabled, setEnabled } = useDeveloperMode();
  const { t } = useTranslation('settings');

  return (
    <div className="space-y-6" data-name="developer-settings-page">
      <PageHeader
        title={t('developer.title')}
        description={t('developer.description')}
      />

      <div
        className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4"
        data-name="developer-mode-toggle"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-sm font-medium text-gray-900 dark:text-white">
              {t('developer.modeTitle')}
            </div>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              {t('developer.modeDescription')}
            </p>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(event) => setEnabled(event.target.checked)}
              className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            {enabled ? t('common:enabled') : t('common:disabled')}
          </label>
        </div>
      </div>
    </div>
  );
};
