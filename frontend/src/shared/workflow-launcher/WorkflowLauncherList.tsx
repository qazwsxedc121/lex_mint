import React from 'react';
import { useTranslation } from 'react-i18next';
import { MagnifyingGlassIcon, StarIcon as StarOutlineIcon } from '@heroicons/react/24/outline';
import { StarIcon as StarSolidIcon } from '@heroicons/react/24/solid';
import type { Workflow } from '../../types/workflow';
import { recommendWorkflows } from './recommend';
import type { LauncherRecentItem, LauncherRecommendationContext, WorkflowLauncherSection } from './types';

interface WorkflowLauncherListProps {
  workflows: Workflow[];
  selectedWorkflowId: string | null;
  loading?: boolean;
  selectionLocked?: boolean;
  namespace: 'projects' | 'workflow';
  compact?: boolean;
  showSearch?: boolean;
  maxWidthClassName?: string;
  headerActions?: React.ReactNode;
  favorites: Set<string>;
  recents: LauncherRecentItem[];
  recommendationContext: LauncherRecommendationContext;
  onSelect: (workflowId: string) => void;
  onToggleFavorite: (workflowId: string) => void;
  renderItemActions?: (workflow: Workflow) => React.ReactNode;
  emptyMessage?: string;
}

const SEARCH_DEBOUNCE_MS = 150;
const COMPACT_LIST_MAX_HEIGHT_CLASS = 'max-h-64 sm:max-h-72';
const DEFAULT_LIST_MAX_HEIGHT_CLASS = 'max-h-96';

const buildSections = (
  workflows: Workflow[],
  recommended: Workflow[],
  recents: LauncherRecentItem[],
  favorites: Set<string>
): WorkflowLauncherSection[] => {
  const byId = new Map(workflows.map((workflow) => [workflow.id, workflow]));
  const recentItems = recents
    .map((item) => byId.get(item.id))
    .filter((item): item is Workflow => Boolean(item));
  const favoriteItems = workflows.filter((workflow) => favorites.has(workflow.id));
  const allItems = workflows;

  const dedupe = (items: Workflow[]): Workflow[] => {
    const seen = new Set<string>();
    return items.filter((item) => {
      if (seen.has(item.id)) {
        return false;
      }
      seen.add(item.id);
      return true;
    });
  };

  const sections: WorkflowLauncherSection[] = [];
  if (recommended.length > 0) {
    sections.push({ key: 'recommended', items: dedupe(recommended) });
  }
  if (recentItems.length > 0) {
    sections.push({ key: 'recent', items: dedupe(recentItems) });
  }
  if (favoriteItems.length > 0) {
    sections.push({ key: 'favorites', items: dedupe(favoriteItems) });
  }
  sections.push({ key: 'all', items: dedupe(allItems) });

  return sections;
};

const sectionDataName = (key: WorkflowLauncherSection['key']): string => {
  return `workflow-launcher-section-${key}`;
};

export const WorkflowLauncherList: React.FC<WorkflowLauncherListProps> = ({
  workflows,
  selectedWorkflowId,
  loading = false,
  selectionLocked = false,
  namespace,
  compact = false,
  showSearch = true,
  maxWidthClassName,
  headerActions,
  favorites,
  recents,
  recommendationContext,
  onSelect,
  onToggleFavorite,
  renderItemActions,
  emptyMessage,
}) => {
  const { t } = useTranslation(namespace);
  const [searchInput, setSearchInput] = React.useState('');
  const [debouncedSearch, setDebouncedSearch] = React.useState('');

  React.useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(searchInput.trim().toLowerCase());
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const visibleWorkflows = React.useMemo(() => {
    const sorted = [...workflows].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    if (!debouncedSearch) {
      return sorted;
    }
    return sorted.filter((workflow) => {
      const haystack = `${workflow.name} ${workflow.id} ${workflow.description || ''}`.toLowerCase();
      return haystack.includes(debouncedSearch);
    });
  }, [debouncedSearch, workflows]);

  const { recommended } = React.useMemo(
    () =>
      recommendWorkflows({
        workflows: visibleWorkflows,
        favorites,
        recents,
        context: recommendationContext,
      }),
    [favorites, recents, recommendationContext, visibleWorkflows]
  );

  const sections = React.useMemo(
    () => buildSections(visibleWorkflows, recommended, recents, favorites),
    [favorites, recents, recommended, visibleWorkflows]
  );
  const [activeSection, setActiveSection] = React.useState<WorkflowLauncherSection['key']>('all');

  React.useEffect(() => {
    if (sections.some((section) => section.key === activeSection)) {
      return;
    }
    if (sections.some((section) => section.key === 'all')) {
      setActiveSection('all');
      return;
    }
    setActiveSection(sections[0]?.key || 'all');
  }, [activeSection, sections]);

  const currentSection = React.useMemo(
    () => sections.find((section) => section.key === activeSection) || sections[0] || null,
    [activeSection, sections]
  );

  const noMatch = !loading && workflows.length > 0 && visibleWorkflows.length === 0;
  const isEmpty = !loading && workflows.length === 0;
  const listClassName = compact
    ? `space-y-1.5 overflow-y-auto overscroll-contain pr-1 ${COMPACT_LIST_MAX_HEIGHT_CLASS}`
    : `space-y-1 overflow-y-auto overscroll-contain pr-1 ${DEFAULT_LIST_MAX_HEIGHT_CLASS}`;

  const renderTabs = () => (
    <div className="flex items-center gap-1 overflow-x-auto" data-name="workflow-launcher-tabs">
      {sections.map((section) => {
        const active = section.key === currentSection?.key;
        return (
          <button
            key={`tab-${section.key}`}
            type="button"
            data-name={`workflow-launcher-tab-${section.key}`}
            onClick={() => setActiveSection(section.key)}
            className={`rounded px-2 py-1 text-xs whitespace-nowrap ${
              active
                ? 'bg-blue-600 text-white'
                : 'border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'
            }`}
          >
            {t(`workflowLauncher.section.${section.key}`)} ({section.items.length})
          </button>
        );
      })}
    </div>
  );

  return (
    <div className={`space-y-3 ${maxWidthClassName || ''}`} data-name="workflow-launcher-list">
      {showSearch ? (
        <div className="flex items-center gap-2">
          <label className="relative block min-w-0 flex-1" data-name="workflow-launcher-search-wrap">
            <MagnifyingGlassIcon className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-gray-400 dark:text-gray-500" />
            <input
              data-name="workflow-launcher-search"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              placeholder={t('workflowLauncher.searchPlaceholder')}
              className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 pl-8 pr-2 py-2 text-sm text-gray-900 dark:text-gray-100"
            />
          </label>
          {renderTabs()}
          {headerActions ? <div className="flex-shrink-0">{headerActions}</div> : null}
        </div>
      ) : null}

      {loading ? (
        <div className="text-sm text-gray-500 dark:text-gray-400">{t('workflowLauncher.loading')}</div>
      ) : isEmpty ? (
        <div className="text-sm text-gray-500 dark:text-gray-400">
          {emptyMessage || t('workflowLauncher.empty')}
        </div>
      ) : noMatch ? (
        <div className="text-sm text-gray-500 dark:text-gray-400">{t('workflowLauncher.noMatch')}</div>
      ) : (
        <div className="space-y-3">
          {!showSearch ? renderTabs() : null}

          {currentSection && (
            <section
              data-name={sectionDataName(currentSection.key)}
              className="space-y-1.5"
            >
              {currentSection.items.length === 0 ? (
                <div className="text-xs text-gray-400 dark:text-gray-500">-</div>
              ) : (
                <ul className={listClassName}>
                  {currentSection.items.map((workflow) => {
                    const isSelected = workflow.id === selectedWorkflowId;
                    const isFavorite = favorites.has(workflow.id);

                    return (
                      <li key={`${currentSection.key}-${workflow.id}`}>
                        <div
                          data-name={`workflow-launcher-item-${workflow.id}`}
                          className={`rounded-md border ${
                            compact ? 'px-2 py-1.5' : 'px-2.5 py-2'
                          } ${
                            isSelected
                              ? 'border-blue-400 bg-blue-50 dark:border-blue-600 dark:bg-blue-900/30'
                              : 'border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900/40'
                          }`}
                        >
                          <div className="flex items-start gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                if (!selectionLocked) {
                                  onSelect(workflow.id);
                                }
                              }}
                              disabled={selectionLocked}
                              className={`min-w-0 flex-1 text-left ${selectionLocked ? 'cursor-not-allowed opacity-70' : ''}`}
                            >
                              <div className="flex items-center gap-2">
                                <span className="truncate text-sm font-medium text-gray-900 dark:text-gray-100">
                                  {workflow.name}
                                </span>
                                {!compact && workflow.is_system && (
                                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                                    {t('workflowLauncher.badge.system')}
                                  </span>
                                )}
                                {!compact && (
                                <span
                                  className={`text-[10px] px-1.5 py-0.5 rounded ${
                                    workflow.enabled
                                      ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                                      : 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
                                  }`}
                                >
                                  {workflow.enabled
                                    ? t('workflowLauncher.badge.enabled')
                                    : t('workflowLauncher.badge.disabled')}
                                </span>
                                )}
                              </div>
                              {!compact && (
                                <div className="mt-1 text-xs text-gray-500 dark:text-gray-400 truncate">
                                  {workflow.id}
                                </div>
                              )}
                              {!compact && workflow.description && (
                                <div className="mt-1 text-xs text-gray-600 dark:text-gray-300 line-clamp-2">
                                  {workflow.description}
                                </div>
                              )}
                            </button>

                            <button
                              type="button"
                              data-name={`workflow-launcher-favorite-${workflow.id}`}
                              onClick={() => onToggleFavorite(workflow.id)}
                              title={
                                isFavorite
                                  ? t('workflowLauncher.favorite.remove')
                                  : t('workflowLauncher.favorite.add')
                              }
                              className={`rounded p-1 ${
                                isFavorite
                                  ? 'text-amber-500 hover:bg-amber-50 dark:hover:bg-amber-900/20'
                                  : 'text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
                              }`}
                            >
                              {isFavorite ? (
                                <StarSolidIcon className="h-4 w-4" />
                              ) : (
                                <StarOutlineIcon className="h-4 w-4" />
                              )}
                            </button>

                            {renderItemActions ? (
                              <div className="flex-shrink-0">{renderItemActions(workflow)}</div>
                            ) : null}
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          )}
        </div>
      )}
    </div>
  );
};
