/**
 * SettingsSidebar - Settings navigation sidebar (Level 2)
 *
 * Provides navigation between settings tabs
 */

import React from 'react';
import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  RocketLaunchIcon,
  UserGroupIcon,
  CpuChipIcon,
  ServerIcon,
  MagnifyingGlassIcon,
  GlobeAltIcon,
  SparklesIcon,
  ChatBubbleLeftRightIcon,
  ArchiveBoxArrowDownIcon,
  LanguageIcon,
  SpeakerWaveIcon,
  BookOpenIcon,
  CircleStackIcon,
  WrenchScrewdriverIcon,
  DocumentTextIcon,
  AtSymbolIcon,
} from '@heroicons/react/24/outline';

interface NavItem {
  path: string;
  labelKey: string;
  icon: React.ForwardRefExoticComponent<React.SVGProps<SVGSVGElement>>;
}

interface NavSection {
  titleKey: string;
  items: NavItem[];
}

export const SettingsSidebar: React.FC = () => {
  const { t } = useTranslation('settings');

  const navSections: NavSection[] = [
    {
      titleKey: 'navGroup.setup',
      items: [
        { path: '/settings/get-started', labelKey: 'nav.getStarted', icon: RocketLaunchIcon },
        { path: '/settings/providers', labelKey: 'nav.providers', icon: ServerIcon },
        { path: '/settings/models', labelKey: 'nav.models', icon: CpuChipIcon },
        { path: '/settings/assistants', labelKey: 'nav.assistants', icon: UserGroupIcon },
      ],
    },
    {
      titleKey: 'navGroup.context',
      items: [
        { path: '/settings/knowledge-bases', labelKey: 'nav.knowledgeBases', icon: BookOpenIcon },
        { path: '/settings/rag', labelKey: 'nav.ragSettings', icon: CircleStackIcon },
        { path: '/settings/prompt-templates', labelKey: 'nav.promptTemplates', icon: DocumentTextIcon },
        { path: '/settings/memory', labelKey: 'nav.memory', icon: CircleStackIcon },
        { path: '/settings/file-reference', labelKey: 'nav.fileReference', icon: AtSymbolIcon },
      ],
    },
    {
      titleKey: 'navGroup.experience',
      items: [
        { path: '/settings/search', labelKey: 'nav.search', icon: MagnifyingGlassIcon },
        { path: '/settings/webpage', labelKey: 'nav.webpage', icon: GlobeAltIcon },
        { path: '/settings/title-generation', labelKey: 'nav.titleGeneration', icon: SparklesIcon },
        { path: '/settings/followup', labelKey: 'nav.followup', icon: ChatBubbleLeftRightIcon },
        { path: '/settings/compression', labelKey: 'nav.compression', icon: ArchiveBoxArrowDownIcon },
      ],
    },
    {
      titleKey: 'navGroup.language',
      items: [
        { path: '/settings/translation', labelKey: 'nav.translation', icon: LanguageIcon },
        { path: '/settings/tts', labelKey: 'nav.tts', icon: SpeakerWaveIcon },
      ],
    },
    {
      titleKey: 'navGroup.developerTools',
      items: [
        { path: '/settings/developer', labelKey: 'nav.developer', icon: WrenchScrewdriverIcon },
      ],
    },
  ];

  return (
    <aside className="w-64 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col">
      {/* Sidebar Header */}
      <div className="h-14 flex items-center px-6 border-b border-gray-200 dark:border-gray-700">
        <h1 className="text-lg font-semibold text-gray-900 dark:text-white">{t('title')}</h1>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-3 overflow-y-auto">
        <div className="space-y-4" data-name="settings-sidebar-groups">
          {navSections.map((section) => (
            <section
              key={section.titleKey}
              data-name="settings-sidebar-group"
              className="border-t border-gray-200 pt-4 first:border-t-0 first:pt-0 dark:border-gray-700"
            >
              <div className="px-3 mb-2">
                <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-gray-500 dark:text-gray-400">
                  {t(section.titleKey)}
                </div>
              </div>
              <ul className="space-y-1">
                {section.items.map((item) => {
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
                        {t(item.labelKey)}
                      </NavLink>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>
      </nav>
    </aside>
  );
};
