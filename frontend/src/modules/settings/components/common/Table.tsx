/**
 * Table Component
 *
 * Generic table with sortable columns and responsive design.
 */

import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { TableColumnConfig } from '../../config/types';

interface TableProps<T> {
  /** Table columns configuration */
  columns: TableColumnConfig<T>[];
  /** Table data rows */
  data: T[];
  /** Context data for cell renderers */
  context?: any;
  /** Row key extractor */
  getRowKey: (row: T) => string;
  /** Row click handler */
  onRowClick?: (row: T) => void;
  /** Empty state message */
  emptyMessage?: string;
}

export function Table<T = any>({
  columns,
  data,
  context = {},
  getRowKey,
  onRowClick,
  emptyMessage
}: TableProps<T>) {
  const { t } = useTranslation('common');
  const resolvedEmptyMessage = emptyMessage ?? t('noData');
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  // Handle column sorting
  const handleSort = (column: TableColumnConfig<T>) => {
    if (!column.sortable) return;

    if (sortKey === column.key) {
      // Toggle direction
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(column.key);
      setSortDirection('asc');
    }
  };

  // Sort data
  const sortedData = React.useMemo(() => {
    if (!sortKey) return data;

    const column = columns.find(col => col.key === sortKey);
    if (!column) return data;

    const sorted = [...data].sort((a, b) => {
      if (column.sortFn) {
        return column.sortFn(a, b);
      }

      // Default sort by key value
      const aVal = (a as any)[column.key];
      const bVal = (b as any)[column.key];

      if (aVal === bVal) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;

      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return aVal.localeCompare(bVal);
      }

      return aVal < bVal ? -1 : 1;
    });

    return sortDirection === 'desc' ? sorted.reverse() : sorted;
  }, [data, sortKey, sortDirection, columns]);

  if (data.length === 0) {
    return (
      <div className="overflow-x-auto" data-name="table">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-900">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  onClick={() => column.onHeaderClick ? column.onHeaderClick() : handleSort(column)}
                  className={`px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider ${
                    column.sortable || column.onHeaderClick ? 'cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800' : ''
                  } ${column.hideOnMobile ? 'hidden md:table-cell' : ''} ${column.width || ''}`}
                >
                  <div className="flex items-center gap-1">
                    {column.label}
                    {column.headerExtra}
                    {column.sortable && sortKey === column.key && (
                      <span className="text-blue-600 dark:text-blue-400">
                        {sortDirection === 'asc' ? '↑' : '↓'}
                      </span>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
        </table>
        <div className="text-center py-12 text-gray-500 dark:text-gray-400">
          {resolvedEmptyMessage}
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto" data-name="table">
      <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
        <thead className="bg-gray-50 dark:bg-gray-900">
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                onClick={() => column.onHeaderClick ? column.onHeaderClick() : handleSort(column)}
                className={`px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider ${
                  column.sortable || column.onHeaderClick ? 'cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800' : ''
                } ${column.hideOnMobile ? 'hidden md:table-cell' : ''} ${column.width || ''}`}
              >
                <div className="flex items-center gap-1">
                  {column.label}
                  {column.headerExtra}
                  {column.sortable && sortKey === column.key && (
                    <span className="text-blue-600 dark:text-blue-400">
                      {sortDirection === 'asc' ? '↑' : '↓'}
                    </span>
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
          {sortedData.map((row) => (
            <tr
              key={getRowKey(row)}
              onClick={() => onRowClick?.(row)}
              className={onRowClick ? 'cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-750' : ''}
            >
              {columns.map((column) => {
                const value = (row as any)[column.key];
                const content = column.render
                  ? column.render(value, row, context)
                  : value;

                return (
                  <td
                    key={column.key}
                    className={`px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400 ${
                      column.hideOnMobile ? 'hidden md:table-cell' : ''
                    }`}
                  >
                    {content}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
