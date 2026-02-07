/**
 * Models Page Configuration
 *
 * Defines the structure and behavior of the Models settings page.
 */

import type { CrudSettingsConfig } from './types';
import type { Model } from '../../../types/model';

export const modelsConfig: CrudSettingsConfig<Model> = {
  type: 'crud',
  title: 'Model List',
  description: 'Manage language models from different providers',
  itemName: 'model',
  itemNamePlural: 'models',

  // Table configuration
  columns: [
    {
      key: 'name',
      label: 'Name',
      sortable: true,
      render: (_value, row) => (
        <div className="text-sm font-medium text-gray-900 dark:text-white">
          {row.name}
        </div>
      )
    },
    {
      key: 'provider_id',
      label: 'Provider',
      sortable: true
    },
    {
      key: 'id',
      label: 'Model ID',
      sortable: true,
      hideOnMobile: true
    },
    {
      key: 'group',
      label: 'Group',
      sortable: true,
      hideOnMobile: true
    }
  ],

  statusKey: 'enabled',

  enableSearch: true,
  searchPlaceholder: 'Search models...',

  // Form fields
  createFields: [
    {
      type: 'text',
      name: 'id',
      label: 'Model ID',
      placeholder: 'e.g., gpt-4',
      required: true,
      helpText: 'Model identifier as used by the provider'
    },
    {
      type: 'select',
      name: 'provider_id',
      label: 'Provider',
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
      helpText: 'Provider that hosts this model'
    },
    {
      type: 'text',
      name: 'name',
      label: 'Display Name',
      placeholder: 'GPT-4',
      required: true,
      helpText: 'Human-readable name for this model'
    },
    {
      type: 'text',
      name: 'group',
      label: 'Group',
      placeholder: 'e.g., gpt-4',
      required: true,
      helpText: 'Model family or group'
    },
    {
      type: 'checkbox',
      name: 'enabled',
      label: 'Enable this model',
      defaultValue: true
    }
  ],

  editFields: [
    {
      type: 'text',
      name: 'id',
      label: 'Model ID',
      required: true,
      disabled: true
    },
    {
      type: 'select',
      name: 'provider_id',
      label: 'Provider',
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
      helpText: 'Provider that hosts this model'
    },
    {
      type: 'text',
      name: 'name',
      label: 'Display Name',
      placeholder: 'GPT-4',
      required: true,
      helpText: 'Human-readable name for this model'
    },
    {
      type: 'text',
      name: 'group',
      label: 'Group',
      placeholder: 'e.g., gpt-4',
      required: true,
      helpText: 'Model family or group'
    },
    {
      type: 'checkbox',
      name: 'enabled',
      label: 'Enable this model',
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
