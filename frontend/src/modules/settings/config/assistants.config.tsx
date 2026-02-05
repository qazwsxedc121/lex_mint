/**
 * Assistants Page Configuration
 *
 * Defines the structure and behavior of the Assistants settings page.
 */

import type { CrudSettingsConfig } from './types';
import type { Assistant } from '../../../types/assistant';

export const assistantsConfig: CrudSettingsConfig<Assistant> = {
  type: 'crud',
  title: 'Assistant List',
  description: 'Configure AI assistants with different models, temperatures, and behaviors',
  itemName: 'assistant',
  itemNamePlural: 'assistants',

  // Table configuration
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
      key: 'model_id',
      label: 'Model',
      sortable: true,
      hideOnMobile: true
    },
    {
      key: 'temperature',
      label: 'Temperature',
      sortable: true,
      hideOnMobile: true,
      render: (value) => value ?? 'Default'
    },
    {
      key: 'max_rounds',
      label: 'Max Rounds',
      sortable: true,
      hideOnMobile: true,
      render: (value) => {
        if (value === -1 || value === null || value === undefined) {
          return 'Unlimited';
        }
        return value;
      }
    }
  ],

  statusKey: 'enabled',
  defaultKey: undefined, // Will use defaultItemId from hook

  enableSearch: true,
  searchPlaceholder: 'Search assistants...',

  // Form fields for create
  createFields: [
    {
      type: 'text',
      name: 'id',
      label: 'Assistant ID',
      placeholder: 'e.g., my-assistant',
      required: true,
      helpText: 'Unique identifier for this assistant'
    },
    {
      type: 'text',
      name: 'name',
      label: 'Name',
      placeholder: 'My Assistant',
      required: true
    },
    {
      type: 'text',
      name: 'description',
      label: 'Description',
      placeholder: 'Optional description',
      helpText: 'Brief description of this assistant'
    },
    {
      type: 'select',
      name: 'model_id',
      label: 'Model',
      required: true,
      dynamicOptions: (context) => {
        const models = context.models || [];
        return models
          .filter((m: any) => m.enabled)
          .map((m: any) => ({
            value: `${m.provider_id}:${m.id}`,
            label: `${m.name} (${m.provider_id}:${m.id})`
          }));
      },
      helpText: 'Language model to use for this assistant'
    },
    {
      type: 'textarea',
      name: 'system_prompt',
      label: 'System Prompt',
      placeholder: 'Optional system prompt...',
      rows: 3,
      helpText: 'Custom instructions for the assistant'
    },
    {
      type: 'slider',
      name: 'temperature',
      label: 'Temperature',
      min: 0,
      max: 2,
      step: 0.1,
      defaultValue: 0.7,
      showValue: true,
      showLabels: true,
      minLabel: '0.0 (Precise)',
      maxLabel: '2.0 (Creative)',
      formatValue: (v) => v.toFixed(1),
      helpText: 'Controls randomness in responses'
    },
    {
      type: 'number',
      name: 'max_rounds',
      label: 'Max Rounds',
      placeholder: '-1 for unlimited',
      min: -1,
      helpText: '-1 or empty = unlimited conversation rounds'
    },
    {
      type: 'checkbox',
      name: 'enabled',
      label: 'Enable this assistant',
      defaultValue: true
    }
  ],

  // Edit fields (id is disabled)
  editFields: [
    {
      type: 'text',
      name: 'id',
      label: 'Assistant ID',
      required: true,
      disabled: true
    },
    {
      type: 'text',
      name: 'name',
      label: 'Name',
      placeholder: 'My Assistant',
      required: true
    },
    {
      type: 'text',
      name: 'description',
      label: 'Description',
      placeholder: 'Optional description',
      helpText: 'Brief description of this assistant'
    },
    {
      type: 'select',
      name: 'model_id',
      label: 'Model',
      required: true,
      dynamicOptions: (context) => {
        const models = context.models || [];
        return models
          .filter((m: any) => m.enabled)
          .map((m: any) => ({
            value: `${m.provider_id}:${m.id}`,
            label: `${m.name} (${m.provider_id}:${m.id})`
          }));
      },
      helpText: 'Language model to use for this assistant'
    },
    {
      type: 'textarea',
      name: 'system_prompt',
      label: 'System Prompt',
      placeholder: 'Optional system prompt...',
      rows: 3,
      helpText: 'Custom instructions for the assistant'
    },
    {
      type: 'slider',
      name: 'temperature',
      label: 'Temperature',
      min: 0,
      max: 2,
      step: 0.1,
      defaultValue: 0.7,
      showValue: true,
      showLabels: true,
      minLabel: '0.0 (Precise)',
      maxLabel: '2.0 (Creative)',
      formatValue: (v) => v.toFixed(1),
      helpText: 'Controls randomness in responses'
    },
    {
      type: 'number',
      name: 'max_rounds',
      label: 'Max Rounds',
      placeholder: '-1 for unlimited',
      min: -1,
      helpText: '-1 or empty = unlimited conversation rounds'
    },
    {
      type: 'checkbox',
      name: 'enabled',
      label: 'Enable this assistant',
      defaultValue: true
    }
  ],

  // Enable default CRUD actions
  enableDefaultActions: {
    create: true,
    edit: true,
    delete: true,
    setDefault: true
  }
};
