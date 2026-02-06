/**
 * SettingsSidebar - Settings navigation sidebar (Level 2)
 *
 * Provides navigation between settings tabs
 */

import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  UserGroupIcon,
  CpuChipIcon,
  ServerIcon,
  MagnifyingGlassIcon,
  GlobeAltIcon,
  SparklesIcon,
  ChatBubbleLeftRightIcon,
} from '@heroicons/react/24/outline';

interface NavItem {
  path: string;
  label: string;
  icon: React.ForwardRefExoticComponent<React.SVGProps<SVGSVGElement>>;
}

const navItems: NavItem[] = [
  { path: '/settings/assistants', label: 'Assistants', icon: UserGroupIcon },
  { path: '/settings/models', label: 'Models', icon: CpuChipIcon },
  { path: '/settings/providers', label: 'Providers', icon: ServerIcon },
  { path: '/settings/search', label: 'Search', icon: MagnifyingGlassIcon },
  { path: '/settings/webpage', label: 'Webpage', icon: GlobeAltIcon },
  { path: '/settings/title-generation', label: 'Title Generation', icon: SparklesIcon },
  { path: '/settings/followup', label: 'Follow-up Questions', icon: ChatBubbleLeftRightIcon },
];

export const SettingsSidebar: React.FC = () => {
  return (
    <aside className="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col">
      {/* Sidebar Header */}
      <div className="h-14 flex items-center px-6 border-b border-gray-200 dark:border-gray-700">
        <h1 className="text-lg font-semibold text-gray-900 dark:text-white">Settings</h1>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-3 overflow-y-auto">
        <ul className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  className={({ isActive }) =>
                    `w-full flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-colors ${
                      isActive
                        ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300'
                        : 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700'
                    }`
                  }
                >
                  <Icon className="h-5 w-5 mr-3" />
                  {item.label}
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
};
