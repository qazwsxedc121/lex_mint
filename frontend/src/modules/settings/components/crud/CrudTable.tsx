/**
 * CrudTable Component
 *
 * Table with filter, actions, and default indicator for CRUD pages.
 */

import { useState, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { PencilIcon, TrashIcon, StarIcon } from '@heroicons/react/24/outline';
import { StarIcon as StarIconSolid } from '@heroicons/react/24/solid';
import { Table, StatusToggle } from '../common';
import type { CrudSettingsConfig, TableColumnConfig, ConfigContext } from '../../config/types';

interface CrudTableProps<T> {
  /** Configuration */
  config: CrudSettingsConfig<T>;
  /** Items to display */
  items: T[];
  /** Default item ID */
  defaultItemId?: string | null;
  /** Edit handler */
  onEdit: (item: T) => void;
  /** Delete handler */
  onDelete: (item: T) => void;
  /** Set default handler */
  onSetDefault?: (item: T) => void;
  /** Toggle status handler */
  onToggleStatus?: (item: T) => void;
  /** Set of item IDs currently being toggled */
  togglingIds?: Set<string>;
  /** Context for cell renderers */
  context: ConfigContext;
  /** Get item ID */
  getItemId: (item: T) => string;
}

export function CrudTable<T = any>({
  config,
  items,
  defaultItemId,
  onEdit,
  onDelete,
  onSetDefault,
  onToggleStatus,
  togglingIds,
  context,
  getItemId
}: CrudTableProps<T>) {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'enabled' | 'disabled'>('all');
  const { t } = useTranslation('settings');

  // Cycle status filter: all → enabled → disabled → all
  const cycleStatusFilter = useCallback(() => {
    setStatusFilter(prev =>
      prev === 'all' ? 'enabled' : prev === 'enabled' ? 'disabled' : 'all'
    );
  }, []);

  // Filter items based on search and status
  const filteredItems = useMemo(() => {
    let result = items;

    // Apply status filter
    if (config.statusKey && statusFilter !== 'all') {
      result = result.filter(item => {
        const enabled = !!(item as any)[config.statusKey!];
        return statusFilter === 'enabled' ? enabled : !enabled;
      });
    }

    // Apply search filter
    if (searchTerm && config.enableSearch) {
      if (config.filterFn) {
        result = result.filter(item => config.filterFn!(item, searchTerm));
      } else {
        result = result.filter(item => {
          const itemStr = JSON.stringify(item).toLowerCase();
          return itemStr.includes(searchTerm.toLowerCase());
        });
      }
    }

    return result;
  }, [items, searchTerm, statusFilter, config]);

  // Build columns with actions
  const columns: TableColumnConfig<T>[] = useMemo(() => {
    const cols = [...config.columns];

    // Add status column if statusKey is provided
    if (config.statusKey) {
      const hasStatusColumn = cols.some(c => c.key === config.statusKey);
      if (!hasStatusColumn) {
        const filterLabel = statusFilter === 'all'
          ? t('common:statusAll')
          : statusFilter === 'enabled'
          ? t('common:enabled')
          : t('common:disabled');

        cols.push({
          key: config.statusKey,
          label: t('common:status'),
          onHeaderClick: cycleStatusFilter,
          headerExtra: (
            <span className={`ml-1 px-1.5 py-0.5 text-[10px] rounded-full normal-case font-normal ${
              statusFilter === 'all'
                ? 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
                : statusFilter === 'enabled'
                ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
                : 'bg-gray-300 text-gray-700 dark:bg-gray-600 dark:text-gray-200'
            }`}>
              {filterLabel}
            </span>
          ),
          render: (value, row) => (
            <StatusToggle
              enabled={!!value}
              onToggle={() => onToggleStatus?.(row)}
              loading={togglingIds?.has(getItemId(row))}
            />
          )
        });
      }
    }

    // Add actions column
    const enabledActions = config.enableDefaultActions || {};
    const showEdit = enabledActions.edit !== false;
    const showDelete = enabledActions.delete !== false;
    const showSetDefault = enabledActions.setDefault !== false && !!onSetDefault;

    if (showEdit || showDelete || showSetDefault || config.rowActions) {
      cols.push({
        key: '__actions',
        label: t('common:actions'),
        render: (_, item) => {
          const itemId = getItemId(item);
          const isDefault = !!(config.defaultKey && (item as any)[config.defaultKey] === true);
          const isDefaultById = !!(defaultItemId && itemId === defaultItemId);
          const isItemDefault = isDefault || isDefaultById;

          return (
            <div className="flex items-center gap-2 justify-end">
              {/* Set Default */}
              {showSetDefault &&
                onSetDefault &&
                (config.defaultActionVisibility?.setDefault
                  ? config.defaultActionVisibility.setDefault(item, context)
                  : true) && (
                <button
                  onClick={() => onSetDefault(item)}
                  disabled={isItemDefault}
                  className="text-yellow-600 hover:text-yellow-900 dark:text-yellow-400 dark:hover:text-yellow-300 disabled:opacity-50 disabled:cursor-not-allowed"
                  title={isItemDefault ? t('crud.alreadyDefault') : t('crud.setAsDefault')}
                >
                  {isItemDefault ? (
                    <StarIconSolid className="h-4 w-4" />
                  ) : (
                    <StarIcon className="h-4 w-4" />
                  )}
                </button>
              )}

              {/* Edit */}
              {showEdit &&
                (config.defaultActionVisibility?.edit
                  ? config.defaultActionVisibility.edit(item, context)
                  : true) && (
                <button
                  onClick={() => onEdit(item)}
                  className="text-blue-600 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-300"
                  title={t('common:edit')}
                >
                  <PencilIcon className="h-4 w-4" />
                </button>
              )}

              {/* Delete */}
              {showDelete &&
                (config.defaultActionVisibility?.delete
                  ? config.defaultActionVisibility.delete(item, context)
                  : true) && (
                <button
                  onClick={() => onDelete(item)}
                  disabled={isItemDefault}
                  className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300 disabled:opacity-50 disabled:cursor-not-allowed"
                  title={isItemDefault ? t('crud.cannotDeleteDefault') : t('common:delete')}
                >
                  <TrashIcon className="h-4 w-4" />
                </button>
              )}

              {/* Custom actions */}
              {config.rowActions?.map((action) => {
                const isDisabled = action.disabled ? action.disabled(item, context) : false;

                const handleClick = async () => {
                  if (action.confirm) {
                    const message = typeof action.confirm.message === 'function'
                      ? action.confirm.message(item)
                      : action.confirm.message;

                    if (!confirm(`${action.confirm.title}\n\n${message}`)) {
                      return;
                    }
                  }

                  await action.onClick(item, context);
                };

                return (
                  <button
                    key={action.id}
                    onClick={handleClick}
                    disabled={isDisabled}
                    className={`${
                      action.variant === 'danger'
                        ? 'text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300'
                        : action.variant === 'warning'
                        ? 'text-yellow-600 hover:text-yellow-900 dark:text-yellow-400 dark:hover:text-yellow-300'
                        : 'text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-300'
                    } disabled:opacity-50 disabled:cursor-not-allowed`}
                    title={action.tooltip}
                  >
                    {action.icon && <action.icon className="h-4 w-4" />}
                    {action.label}
                  </button>
                );
              })}
            </div>
          );
        }
      });
    }

    return cols;
  }, [config, defaultItemId, onEdit, onDelete, onSetDefault, onToggleStatus, togglingIds, statusFilter, cycleStatusFilter, context, getItemId, t]);

  return (
    <div data-name="crud-table">
      {/* Search bar */}
      {config.enableSearch !== false && (
        <div className="mb-4">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder={config.searchPlaceholder || t('crud.searchItems', { items: config.itemNamePlural || config.itemName + 's' })}
            className="w-full max-w-md px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500"
          />
        </div>
      )}

      {/* Table */}
      <Table
        columns={columns}
        data={filteredItems}
        context={context}
        getRowKey={getItemId}
        emptyMessage={t('crud.noItemsFound', { items: config.itemNamePlural || config.itemName + 's' })}
      />
    </div>
  );
}
