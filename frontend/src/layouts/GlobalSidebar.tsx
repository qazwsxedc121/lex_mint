/**
 * GlobalSidebar - Collapsible global navigation (Level 1)
 *
 * Provides navigation between main modules (Chat, Settings)
 */

import React from 'react';
import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  ChatBubbleLeftRightIcon,
  FolderIcon,
  Cog6ToothIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  WrenchScrewdriverIcon,
} from '@heroicons/react/24/outline';
import { useDeveloperMode } from '../hooks/useDeveloperMode';
import { LanguageSwitcher } from '../i18n/components/LanguageSwitcher';

interface GlobalSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

interface NavItem {
  path: string;
  labelKey: string;
  icon: React.ForwardRefExoticComponent<React.SVGProps<SVGSVGElement>>;
}

export const GlobalSidebar: React.FC<GlobalSidebarProps> = ({
  collapsed,
  onToggle,
}) => {
  const { t } = useTranslation('common');
  const { enabled: developerEnabled } = useDeveloperMode();
  const navItems: NavItem[] = [
    { path: '/chat', labelKey: 'nav.chat', icon: ChatBubbleLeftRightIcon },
    { path: '/projects', labelKey: 'nav.projects', icon: FolderIcon },
    ...(developerEnabled ? [{ path: '/developer', labelKey: 'nav.developer', icon: WrenchScrewdriverIcon }] : []),
    { path: '/settings', labelKey: 'nav.settings', icon: Cog6ToothIcon },
  ];

  return (
    <aside
      className={`flex flex-col bg-gray-900 text-white transition-all duration-200 ${
        collapsed ? 'w-16' : 'w-48'
      }`}
    >
      {/* Logo / Brand */}
      <div className="h-14 flex items-center justify-center border-b border-gray-700">
        {collapsed ? (
          <span className="text-xl font-bold">A</span>
        ) : (
          <span className="text-lg font-semibold">Agent</span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4">
        <ul className="space-y-1 px-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const label = t(item.labelKey);
            return (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
                      isActive
                        ? 'bg-blue-600 text-white'
                        : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                    }`
                  }
                  title={collapsed ? label : undefined}
                >
                  <Icon className="h-5 w-5 flex-shrink-0" />
                  {!collapsed && (
                    <span className="text-sm font-medium">{label}</span>
                  )}
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Language Switcher + Collapse Toggle */}
      <div className="border-t border-gray-700 p-2 space-y-1">
        <LanguageSwitcher collapsed={collapsed} />
        <button
          onClick={onToggle}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
          title={collapsed ? t('expand') : t('collapse')}
        >
          {collapsed ? (
            <ChevronRightIcon className="h-5 w-5" />
          ) : (
            <>
              <ChevronLeftIcon className="h-5 w-5" />
              <span className="text-sm">{t('collapse')}</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
};
