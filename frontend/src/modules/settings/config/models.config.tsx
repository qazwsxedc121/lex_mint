/**
 * Models Page Configuration
 *
 * Defines the structure and behavior of the Models settings page.
 */

import type { CrudSettingsConfig } from './types';
import type { Model } from '../../../types/model';
import i18n from '../../../i18n';

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
      key: 'group',
      get label() { return i18n.t('settings:models.col.group'); },
      sortable: true,
      hideOnMobile: true
    }
  ],

  statusKey: 'enabled',

  enableSearch: true,
  get searchPlaceholder() { return i18n.t('settings:models.search'); },

  // Form fields
  createFields: [
    {
      type: 'text',
      name: 'id',
      get label() { return i18n.t('settings:models.field.id'); },
      get placeholder() { return i18n.t('settings:models.field.id.placeholder'); },
      required: true,
      get helpText() { return i18n.t('settings:models.field.id.help'); }
    },
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
      type: 'text',
      name: 'name',
      get label() { return i18n.t('settings:models.field.name'); },
      get placeholder() { return i18n.t('settings:models.field.name.placeholder'); },
      required: true,
      get helpText() { return i18n.t('settings:models.field.name.help'); }
    },
    {
      type: 'text',
      name: 'group',
      get label() { return i18n.t('settings:models.field.group'); },
      get placeholder() { return i18n.t('settings:models.field.group.placeholder'); },
      required: true,
      get helpText() { return i18n.t('settings:models.field.group.help'); }
    },
    {
      type: 'checkbox',
      name: 'enabled',
      get label() { return i18n.t('settings:models.field.enabled'); },
      defaultValue: true
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
      name: 'group',
      get label() { return i18n.t('settings:models.field.group'); },
      get placeholder() { return i18n.t('settings:models.field.group.placeholder'); },
      required: true,
      get helpText() { return i18n.t('settings:models.field.group.help'); }
    },
    {
      type: 'checkbox',
      name: 'enabled',
      get label() { return i18n.t('settings:models.field.enabled'); },
      defaultValue: true
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
