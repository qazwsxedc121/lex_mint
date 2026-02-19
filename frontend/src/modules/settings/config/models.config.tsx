/**
 * Models Page Configuration
 *
 * Defines the structure and behavior of the Models settings page.
 */

import { SignalIcon } from '@heroicons/react/24/outline';
import type { CrudSettingsConfig } from './types';
import type { Model } from '../../../types/model';
import { testModelConnection } from '../../../services/api';
import i18n from '../../../i18n';

const normalizeTags = (rawValue: unknown): string[] => {
  if (Array.isArray(rawValue)) {
    return rawValue
      .map((tag) => String(tag).trim().toLowerCase())
      .filter(Boolean);
  }
  if (typeof rawValue === 'string') {
    return rawValue
      .split(',')
      .map((tag) => tag.trim().toLowerCase())
      .filter(Boolean);
  }
  return [];
};

export const modelsConfig: CrudSettingsConfig<Model> = {
  type: 'crud',
  get title() { return i18n.t('settings:models.title'); },
  get description() { return i18n.t('settings:models.description'); },
  get itemName() { return i18n.t('settings:models.itemName'); },
  get itemNamePlural() { return i18n.t('settings:models.itemNamePlural'); },
  createMode: 'page',
  createPath: '/settings/models/new',
  editMode: 'page',
  editPath: (itemId) => `/settings/models/${encodeURIComponent(itemId)}`,

  // Table configuration
  columns: [
    {
      key: 'name',
      get label() { return i18n.t('settings:models.col.name'); },
      sortable: true,
      render: (_value, row) => (
        <div className="text-sm font-medium text-gray-900 dark:text-white">
          {row.name}
        </div>
      )
    },
    {
      key: 'provider_id',
      get label() { return i18n.t('settings:models.col.provider'); },
      sortable: true
    },
    {
      key: 'id',
      get label() { return i18n.t('settings:models.col.modelId'); },
      sortable: true,
      hideOnMobile: true
    },
    {
      key: 'tags',
      get label() { return i18n.t('settings:models.col.tags'); },
      sortable: true,
      hideOnMobile: true,
      sortFn: (a, b) => normalizeTags(a.tags).join(',').localeCompare(normalizeTags(b.tags).join(',')),
      render: (value) => {
        const tags = normalizeTags(value);
        if (tags.length === 0) {
          return <span className="text-gray-400 dark:text-gray-500">-</span>;
        }
        return (
          <div className="flex flex-wrap gap-1">
            {tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-700 dark:bg-gray-700 dark:text-gray-200"
              >
                {tag}
              </span>
            ))}
          </div>
        );
      }
    }
  ],

  statusKey: 'enabled',

  enableSearch: true,
  get searchPlaceholder() { return i18n.t('settings:models.search'); },

  // Form fields
  createFields: [
    {
      type: 'select',
      name: 'provider_id',
      get label() { return i18n.t('settings:models.field.providerId'); },
      required: true,
      dynamicOptions: (context) => {
        const providers = context.providers || [];
        return providers
          .filter((p: any) => p.enabled)
          .map((p: any) => ({
            value: p.id,
            label: `${p.name} (${p.id})`
          }));
      },
      get helpText() { return i18n.t('settings:models.field.providerId.help'); }
    },
    {
      type: 'model-id',
      name: 'id',
      get label() { return i18n.t('settings:models.field.id'); },
      get placeholder() { return i18n.t('settings:models.field.id.placeholder'); },
      required: true,
      get helpText() { return i18n.t('settings:models.field.id.help'); },
      condition: (formData) => !!formData.provider_id,
    },
    {
      type: 'text',
      name: 'name',
      get label() { return i18n.t('settings:models.field.name'); },
      get placeholder() { return i18n.t('settings:models.field.name.placeholder'); },
      required: true,
      get helpText() { return i18n.t('settings:models.field.name.help'); },
      condition: (formData) => !!formData.provider_id,
    },
    {
      type: 'text',
      name: 'tags',
      get label() { return i18n.t('settings:models.field.tags'); },
      get placeholder() { return i18n.t('settings:models.field.tags.placeholder'); },
      get helpText() { return i18n.t('settings:models.field.tags.help'); },
      condition: (formData) => !!formData.provider_id,
    },
    {
      type: 'checkbox',
      name: 'enabled',
      get label() { return i18n.t('settings:models.field.enabled'); },
      defaultValue: true,
      condition: (formData) => !!formData.provider_id,
    }
  ],

  editFields: [
    {
      type: 'text',
      name: 'id',
      get label() { return i18n.t('settings:models.field.id'); },
      required: true,
      disabled: true
    },
    {
      type: 'select',
      name: 'provider_id',
      get label() { return i18n.t('settings:models.field.providerId'); },
      required: true,
      disabled: true,
      dynamicOptions: (context) => {
        const providers = context.providers || [];
        return providers
          .map((p: any) => ({
            value: p.id,
            label: `${p.name} (${p.id})`
          }));
      },
      get helpText() { return i18n.t('settings:models.field.providerId.help'); }
    },
    {
      type: 'text',
      name: 'name',
      get label() { return i18n.t('settings:models.field.name'); },
      get placeholder() { return i18n.t('settings:models.field.name.placeholder'); },
      required: true,
      get helpText() { return i18n.t('settings:models.field.name.help'); }
    },
    {
      type: 'text',
      name: 'tags',
      get label() { return i18n.t('settings:models.field.tags'); },
      get placeholder() { return i18n.t('settings:models.field.tags.placeholder'); },
      get helpText() { return i18n.t('settings:models.field.tags.help'); }
    },
    {
      type: 'checkbox',
      name: 'enabled',
      get label() { return i18n.t('settings:models.field.enabled'); },
      defaultValue: true
    }
  ],

  // Row actions
  rowActions: [
    {
      id: 'test-connection',
      label: '',
      icon: SignalIcon,
      get tooltip() { return i18n.t('settings:models.action.testConnection'); },
      onClick: async (item: Model) => {
        try {
          const result = await testModelConnection(`${item.provider_id}:${item.id}`);
          if (result.success) {
            alert(i18n.t('settings:testConnection.success') + '\n' + result.message);
          } else {
            alert(i18n.t('settings:testConnection.failed') + '\n' + result.message);
          }
        } catch (err: any) {
          alert(i18n.t('settings:testConnection.failed') + '\n' + (err.message || String(err)));
        }
      }
    }
  ],

  // Enable default CRUD actions
  enableDefaultActions: {
    create: true,
    edit: true,
    delete: true,
    setDefault: false // Models don't have a default
  }
};
