/**
 * Prompt Templates Page Configuration
 */

import type { CrudSettingsConfig } from './types';
import type { PromptTemplate, PromptTemplateVariable } from '../../../types/promptTemplate';
import i18n from '../../../i18n';

const VARIABLE_KEY_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/;
const TRIGGER_PATTERN = /^[a-z0-9][a-z0-9_-]*$/;

const normalizeTrigger = (value: unknown): string => (typeof value === 'string' ? value.trim() : '');

const normalizeAliases = (value: unknown): string[] => {
  const source = Array.isArray(value)
    ? value
    : typeof value === 'string'
      ? value.split(/[\n,]/)
      : [];

  const normalized: string[] = [];
  const seen = new Set<string>();
  for (const item of source) {
    const alias = String(item).trim();
    if (!alias) {
      continue;
    }
    const lowered = alias.toLowerCase();
    if (seen.has(lowered)) {
      continue;
    }
    seen.add(lowered);
    normalized.push(alias);
  }
  return normalized;
};

const validateTrigger = (value: unknown): string | undefined => {
  const trigger = normalizeTrigger(value);
  if (!trigger) {
    return undefined;
  }
  if (!TRIGGER_PATTERN.test(trigger)) {
    return i18n.t('settings:promptTemplates.field.trigger.errorFormat');
  }
  return undefined;
};

const validateAliases = (value: unknown): string | undefined => {
  const aliases = normalizeAliases(value);
  for (const alias of aliases) {
    if (!TRIGGER_PATTERN.test(alias)) {
      return i18n.t('settings:promptTemplates.field.aliases.errorFormat');
    }
  }
  return undefined;
};

const shouldShowAdvancedFields = (formData: Record<string, unknown>): boolean => {
  if (formData.__showAdvanced === true) {
    return true;
  }
  const trigger = normalizeTrigger(formData.trigger);
  if (trigger) {
    return true;
  }
  const aliases = normalizeAliases(formData.aliases);
  return aliases.length > 0;
};

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
  modalSize: 'xl',
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
      key: 'trigger',
      get label() { return i18n.t('settings:promptTemplates.col.trigger'); },
      sortable: true,
      hideOnMobile: true,
      render: (value) => (
        <div className="text-xs text-gray-600 dark:text-gray-300">
          {value ? `/${String(value)}` : '-'}
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
    const aliases = Array.isArray(item.aliases) ? item.aliases.join(' ') : '';
    return (
      item.id.toLowerCase().includes(query) ||
      item.name.toLowerCase().includes(query) ||
      (item.description || '').toLowerCase().includes(query) ||
      (item.trigger || '').toLowerCase().includes(query) ||
      aliases.toLowerCase().includes(query) ||
      item.content.toLowerCase().includes(query)
    );
  },

  validateForm: (formData) => {
    const trigger = normalizeTrigger(formData.trigger);
    const aliases = normalizeAliases(formData.aliases);
    if (!trigger) {
      return undefined;
    }
    const triggerLower = trigger.toLowerCase();
    if (aliases.some((alias) => alias.toLowerCase() === triggerLower)) {
      return i18n.t('settings:promptTemplates.field.aliases.errorConflict');
    }
    return undefined;
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
      type: 'checkbox',
      name: '__showAdvanced',
      get label() { return i18n.t('settings:promptTemplates.field.advanced.label'); },
      defaultValue: false,
    },
    {
      type: 'text',
      name: 'trigger',
      get label() { return i18n.t('settings:promptTemplates.field.trigger.label'); },
      get placeholder() { return i18n.t('settings:promptTemplates.field.trigger.placeholder'); },
      get helpText() { return i18n.t('settings:promptTemplates.field.trigger.help'); },
      validate: validateTrigger,
      condition: (formData) => shouldShowAdvancedFields(formData as Record<string, unknown>),
    },
    {
      type: 'textarea',
      name: 'aliases',
      get label() { return i18n.t('settings:promptTemplates.field.aliases.label'); },
      get placeholder() { return i18n.t('settings:promptTemplates.field.aliases.placeholder'); },
      get helpText() { return i18n.t('settings:promptTemplates.field.aliases.help'); },
      validate: validateAliases,
      rows: 3,
      condition: (formData) => shouldShowAdvancedFields(formData as Record<string, unknown>),
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
    {
      type: 'checkbox',
      name: '__showAdvanced',
      get label() { return i18n.t('settings:promptTemplates.field.advanced.label'); },
      defaultValue: false,
    },
    {
      type: 'text',
      name: 'trigger',
      get label() { return i18n.t('settings:promptTemplates.field.trigger.label'); },
      get helpText() { return i18n.t('settings:promptTemplates.field.trigger.help'); },
      validate: validateTrigger,
      condition: (formData) => shouldShowAdvancedFields(formData as Record<string, unknown>),
    },
    {
      type: 'textarea',
      name: 'aliases',
      get label() { return i18n.t('settings:promptTemplates.field.aliases.label'); },
      get helpText() { return i18n.t('settings:promptTemplates.field.aliases.help'); },
      validate: validateAliases,
      rows: 3,
      condition: (formData) => shouldShowAdvancedFields(formData as Record<string, unknown>),
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
