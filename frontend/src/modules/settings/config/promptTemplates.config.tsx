/**
 * Prompt Templates Page Configuration
 */

import type { CrudSettingsConfig } from './types';
import type { PromptTemplate } from '../../../types/promptTemplate';
import i18n from '../../../i18n';

export const promptTemplatesConfig: CrudSettingsConfig<PromptTemplate> = {
  type: 'crud',
  title: 'Prompt Templates',
  description: 'Manage reusable prompt templates for quick insertion.',
  itemName: 'template',
  itemNamePlural: 'templates',

  columns: [
    {
      key: 'name',
      label: 'Name',
      sortable: true,
      render: (_value, row) => (
        <div>
          <div className="text-sm font-medium text-gray-900 dark:text-white">
            {row.name}
          </div>
          {row.description && (
            <div className="text-xs text-gray-500 dark:text-gray-400">
              {row.description}
            </div>
          )}
        </div>
      )
    },
    {
      key: 'content',
      label: 'Content',
      sortable: false,
      hideOnMobile: true,
      render: (value) => (
        <div className="text-xs text-gray-500 dark:text-gray-400 truncate max-w-xs">
          {String(value || '').slice(0, 120)}
        </div>
      )
    },
    {
      key: 'enabled',
      label: 'Enabled',
      sortable: true,
      hideOnMobile: true,
      render: (value) => (value ? i18n.t('common:yes') : i18n.t('common:no'))
    }
  ],

  statusKey: 'enabled',
  enableSearch: true,
  searchPlaceholder: 'Search templates...',
  filterFn: (item, term) => {
    const query = term.toLowerCase();
    return (
      item.id.toLowerCase().includes(query) ||
      item.name.toLowerCase().includes(query) ||
      (item.description || '').toLowerCase().includes(query) ||
      item.content.toLowerCase().includes(query)
    );
  },

  createFields: [
    {
      type: 'text',
      name: 'name',
      label: 'Name',
      placeholder: 'Code Review Template',
      required: true
    },
    {
      type: 'text',
      name: 'description',
      label: 'Description',
      placeholder: 'Short summary of when to use this template'
    },
    {
      type: 'textarea',
      name: 'content',
      label: 'Content',
      placeholder: 'Write the prompt template here...',
      required: true,
      rows: 10,
      monospace: true
    },
    {
      type: 'checkbox',
      name: 'enabled',
      label: 'Enabled',
      defaultValue: true
    }
  ],

  editFields: [
    {
      type: 'text',
      name: 'name',
      label: 'Name',
      required: true
    },
    {
      type: 'text',
      name: 'description',
      label: 'Description'
    },
    {
      type: 'textarea',
      name: 'content',
      label: 'Content',
      required: true,
      rows: 10,
      monospace: true
    },
    {
      type: 'checkbox',
      name: 'enabled',
      label: 'Enabled'
    }
  ],
};
