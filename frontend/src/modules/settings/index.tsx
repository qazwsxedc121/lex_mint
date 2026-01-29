/**
 * SettingsModule - Main entry point for the settings module
 *
 * Contains SettingsSidebar and outlet for settings pages
 */

import React from 'react';
import { Outlet } from 'react-router-dom';
import { SettingsSidebar } from './SettingsSidebar';

export const SettingsModule: React.FC = () => {
  return (
    <div className="flex flex-1 bg-gray-100 dark:bg-gray-900">
      {/* Settings Sidebar (Level 2) */}
      <SettingsSidebar />

      {/* Settings Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  );
};
