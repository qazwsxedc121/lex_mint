/**
 * Prompt Templates Page Configuration
 */

import type { CrudSettingsConfig } from './types';
import type { PromptTemplate } from '../../../types/promptTemplate';
import i18n from '../../../i18n';

export const promptTemplatesConfig: CrudSettingsConfig<PromptTemplate> = {
  type: 'crud',
  get title() { return i18n.t('settings:promptTemplates.title'); },
  get description() { return i18n.t('settings:promptTemplates.description'); },
  get itemName() { return i18n.t('settings:promptTemplates.itemName'); },
  get itemNamePlural() { return i18n.t('settings:promptTemplates.itemNamePlural'); },

  columns: [
    {
      key: 'name',
      get label() { return i18n.t('settings:promptTemplates.col.name'); },
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
      get label() { return i18n.t('settings:promptTemplates.col.content'); },
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
      get label() { return i18n.t('settings:promptTemplates.col.enabled'); },
      sortable: true,
      hideOnMobile: true,
      render: (value) => (value ? i18n.t('common:yes') : i18n.t('common:no'))
    }
  ],

  statusKey: 'enabled',
  enableSearch: true,
  get searchPlaceholder() { return i18n.t('settings:promptTemplates.search'); },
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
      get label() { return i18n.t('settings:promptTemplates.field.name'); },
      get placeholder() { return i18n.t('settings:promptTemplates.field.name.placeholder'); },
      required: true
    },
    {
      type: 'text',
      name: 'description',
      get label() { return i18n.t('settings:promptTemplates.field.description'); },
      get placeholder() { return i18n.t('settings:promptTemplates.field.description.placeholder'); }
    },
    {
      type: 'textarea',
      name: 'content',
      get label() { return i18n.t('settings:promptTemplates.field.content'); },
      get placeholder() { return i18n.t('settings:promptTemplates.field.content.placeholder'); },
      required: true,
      rows: 10,
      monospace: true
    },
    {
      type: 'checkbox',
      name: 'enabled',
      get label() { return i18n.t('settings:promptTemplates.field.enabled'); },
      defaultValue: true
    }
  ],

  editFields: [
    {
      type: 'text',
      name: 'name',
      get label() { return i18n.t('settings:promptTemplates.field.name'); },
      required: true
    },
    {
      type: 'text',
      name: 'description',
      get label() { return i18n.t('settings:promptTemplates.field.description'); }
    },
    {
      type: 'textarea',
      name: 'content',
      get label() { return i18n.t('settings:promptTemplates.field.content'); },
      required: true,
      rows: 10,
      monospace: true
    },
    {
      type: 'checkbox',
      name: 'enabled',
      get label() { return i18n.t('settings:promptTemplates.field.enabled'); }
    }
  ],
};
