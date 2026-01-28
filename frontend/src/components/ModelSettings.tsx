/**
 * Settings Page - Full Screen Layout
 *
 * Full-screen settings page with tree navigation sidebar
 */

import React, { useState } from 'react';
import {
  XMarkIcon,
  UserGroupIcon,
  CpuChipIcon,
  ServerIcon,
  Cog6ToothIcon,
} from '@heroicons/react/24/outline';
import { ProviderList } from './ProviderList';
import { ModelList } from './ModelList';
import { AssistantList } from './AssistantList';
import { useModels } from '../hooks/useModels';
import { useAssistants } from '../hooks/useAssistants';

interface ModelSettingsProps {
  isOpen: boolean;
  onClose: () => void;
}

type TabType = 'assistants' | 'models' | 'providers';

interface MenuItem {
  key: TabType;
  label: string;
  icon: React.ForwardRefExoticComponent<React.SVGProps<SVGSVGElement>>;
}

const menuItems: MenuItem[] = [
  { key: 'assistants', label: 'Assistants', icon: UserGroupIcon },
  { key: 'models', label: 'Models', icon: CpuChipIcon },
  { key: 'providers', label: 'Providers', icon: ServerIcon },
];

export const ModelSettings: React.FC<ModelSettingsProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<TabType>('assistants');
  const modelsHook = useModels();
  const assistantsHook = useAssistants();

  if (!isOpen) return null;

  const activeMenuItem = menuItems.find(item => item.key === activeTab);

  return (
    <div className="fixed inset-0 z-50 flex bg-gray-100 dark:bg-gray-900">
      {/* Left: Tree Navigation Sidebar */}
      <aside className="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col">
        {/* Sidebar Header */}
        <div className="h-16 flex items-center px-6 border-b border-gray-200 dark:border-gray-700">
          <Cog6ToothIcon className="h-6 w-6 text-gray-500 dark:text-gray-400 mr-3" />
          <h1 className="text-lg font-semibold text-gray-900 dark:text-white">Settings</h1>
        </div>

        {/* Tree Navigation */}
        <nav className="flex-1 py-4 px-3 overflow-y-auto">
          <ul className="space-y-1">
            {menuItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.key;
              return (
                <li key={item.key}>
                  <button
                    onClick={() => setActiveTab(item.key)}
                    className={`w-full flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-colors ${
                      isActive
                        ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300'
                        : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'
                    }`}
                  >
                    <Icon className={`h-5 w-5 mr-3 ${
                      isActive
                        ? 'text-blue-600 dark:text-blue-400'
                        : 'text-gray-400 dark:text-gray-500'
                    }`} />
                    {item.label}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
      </aside>

      {/* Right: Content Area */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Content Header */}
        <div className="h-16 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between px-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            {activeMenuItem?.label || 'Settings'}
          </h2>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-500 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            title="Close settings"
          >
            <XMarkIcon className="h-6 w-6" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6">
          {(modelsHook.loading || assistantsHook.loading) ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-gray-500 dark:text-gray-400">Loading...</div>
            </div>
          ) : (modelsHook.error || assistantsHook.error) ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-red-500">{modelsHook.error || assistantsHook.error}</div>
            </div>
          ) : (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
              {activeTab === 'assistants' && (
                <AssistantList
                  assistants={assistantsHook.assistants}
                  defaultAssistantId={assistantsHook.defaultAssistantId}
                  models={modelsHook.models}
                  onCreateAssistant={assistantsHook.createAssistant}
                  onUpdateAssistant={assistantsHook.updateAssistant}
                  onDeleteAssistant={assistantsHook.deleteAssistant}
                  onSetDefault={assistantsHook.setDefaultAssistant}
                />
              )}
              {activeTab === 'models' && <ModelList {...modelsHook} />}
              {activeTab === 'providers' && <ProviderList {...modelsHook} />}
            </div>
          )}
        </div>
      </main>
    </div>
  );
};
