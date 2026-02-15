/**
 * Prompt Templates Page Configuration
 */

import type { CrudSettingsConfig } from './types';
import type { PromptTemplate, PromptTemplateVariable } from '../../../types/promptTemplate';
import i18n from '../../../i18n';

const VARIABLE_KEY_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/;

const validateVariables = (value: unknown): string | undefined => {
  if (value == null) {
    return undefined;
  }

  if (!Array.isArray(value)) {
    return i18n.t('settings:promptTemplates.field.variables.error');
  }

  const seen = new Set<string>();
  for (const variable of value as PromptTemplateVariable[]) {
    if (!variable || typeof variable !== 'object') {
      return i18n.t('settings:promptTemplates.field.variables.error');
    }

    const key = typeof variable.key === 'string' ? variable.key.trim() : '';
    if (!key || !VARIABLE_KEY_PATTERN.test(key)) {
      return i18n.t('settings:promptTemplates.field.variables.errorKey');
    }
    if (key.toLowerCase() === 'cursor') {
      return i18n.t('settings:promptTemplates.field.variables.errorReserved');
    }
    if (seen.has(key)) {
      return i18n.t('settings:promptTemplates.field.variables.errorDuplicate');
    }
    seen.add(key);

    const type = variable.type || 'text';
    if (!['text', 'number', 'boolean', 'select'].includes(type)) {
      return i18n.t('settings:promptTemplates.field.variables.errorType');
    }

    const options = Array.isArray(variable.options)
      ? variable.options.map((item) => String(item).trim()).filter(Boolean)
      : [];
    if (type === 'select' && options.length === 0) {
      return i18n.t('settings:promptTemplates.field.variables.errorSelectOptions');
    }
    if (type !== 'select' && options.length > 0) {
      return i18n.t('settings:promptTemplates.field.variables.errorOptionsOnlySelect');
    }

    if (variable.default !== undefined && variable.default !== null) {
      if (type === 'text' && typeof variable.default !== 'string') {
        return i18n.t('settings:promptTemplates.field.variables.errorDefaultType');
      }
      if (type === 'number' && (typeof variable.default !== 'number' || !Number.isFinite(variable.default))) {
        return i18n.t('settings:promptTemplates.field.variables.errorDefaultType');
      }
      if (type === 'boolean' && typeof variable.default !== 'boolean') {
        return i18n.t('settings:promptTemplates.field.variables.errorDefaultType');
      }
      if (type === 'select') {
        if (typeof variable.default !== 'string') {
          return i18n.t('settings:promptTemplates.field.variables.errorDefaultType');
        }
        if (!options.includes(variable.default)) {
          return i18n.t('settings:promptTemplates.field.variables.errorSelectDefault');
        }
      }
    }
  }

  return undefined;
};

const variablesField = {
  type: 'template-variables' as const,
  name: 'variables',
  get label() { return i18n.t('settings:promptTemplates.field.variables.label'); },
  get helpText() { return i18n.t('settings:promptTemplates.field.variables.help'); },
  defaultValue: [],
  validate: validateVariables,
};

const contentField = (isEdit: boolean) => ({
  type: 'textarea' as const,
  name: 'content',
  get label() { return i18n.t('settings:promptTemplates.field.content'); },
  ...(isEdit ? {} : {
    get placeholder() { return i18n.t('settings:promptTemplates.field.content.placeholder'); },
  }),
  required: true,
  rows: 10,
  monospace: true,
});

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
    contentField(false),
    variablesField,
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
    contentField(true),
    variablesField,
    {
      type: 'checkbox',
      name: 'enabled',
      get label() { return i18n.t('settings:promptTemplates.field.enabled'); }
    }
  ],
};
