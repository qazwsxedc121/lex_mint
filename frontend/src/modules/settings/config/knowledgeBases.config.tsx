/**
 * Knowledge Bases Page Configuration
 *
 * Defines the structure and behavior of the Knowledge Bases settings page.
 */

import type { CrudSettingsConfig } from './types';
import type { KnowledgeBase } from '../../../types/knowledgeBase';
import i18n from '../../../i18n';

export const knowledgeBasesConfig: CrudSettingsConfig<KnowledgeBase> = {
  type: 'crud',
  get title() { return i18n.t('settings:knowledgeBases.title'); },
  get description() { return i18n.t('settings:knowledgeBases.description'); },
  get itemName() { return i18n.t('settings:knowledgeBases.itemName'); },
  get itemNamePlural() { return i18n.t('settings:knowledgeBases.itemNamePlural'); },
  createMode: 'page',
  createPath: '/settings/knowledge-bases/new',
  editMode: 'page',
  editPath: (itemId) => `/settings/knowledge-bases/${itemId}`,

  // Table configuration
  columns: [
    {
      key: 'name',
      get label() { return i18n.t('settings:knowledgeBases.col.name'); },
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
      key: 'document_count',
      get label() { return i18n.t('settings:knowledgeBases.col.documents'); },
      sortable: true,
      hideOnMobile: true,
      render: (value) => value || 0
    },
    {
      key: 'created_at',
      get label() { return i18n.t('settings:knowledgeBases.col.created'); },
      sortable: true,
      hideOnMobile: true,
      render: (value) => {
        if (!value) return '';
        try {
          return new Date(value).toLocaleDateString();
        } catch {
          return value;
        }
      }
    }
  ],

  statusKey: 'enabled',

  enableSearch: true,
  get searchPlaceholder() { return i18n.t('settings:knowledgeBases.search'); },

  // Form fields for create
  createFields: [
    {
      type: 'text',
      name: 'id',
      get label() { return i18n.t('settings:knowledgeBases.field.id'); },
      get placeholder() { return i18n.t('settings:knowledgeBases.field.id.placeholder'); },
      required: true,
      get helpText() { return i18n.t('settings:knowledgeBases.field.id.help'); }
    },
    {
      type: 'text',
      name: 'name',
      get label() { return i18n.t('settings:knowledgeBases.field.name'); },
      get placeholder() { return i18n.t('settings:knowledgeBases.field.name.placeholder'); },
      required: true
    },
    {
      type: 'text',
      name: 'description',
      get label() { return i18n.t('settings:knowledgeBases.field.description'); },
      get placeholder() { return i18n.t('settings:knowledgeBases.field.description.placeholder'); },
      get helpText() { return i18n.t('settings:knowledgeBases.field.description.help'); }
    },
    {
      type: 'text',
      name: 'embedding_model',
      get label() { return i18n.t('settings:knowledgeBases.field.embeddingModel'); },
      get placeholder() { return i18n.t('settings:knowledgeBases.field.embeddingModel.placeholder'); },
      get helpText() { return i18n.t('settings:knowledgeBases.field.embeddingModel.help'); }
    },
    {
      type: 'number',
      name: 'chunk_size',
      get label() { return i18n.t('settings:knowledgeBases.field.chunkSize'); },
      get placeholder() { return i18n.t('settings:knowledgeBases.field.chunkSize.placeholder'); },
      min: 100,
      max: 10000,
      get helpText() { return i18n.t('settings:knowledgeBases.field.chunkSize.help'); }
    },
    {
      type: 'number',
      name: 'chunk_overlap',
      get label() { return i18n.t('settings:knowledgeBases.field.chunkOverlap'); },
      get placeholder() { return i18n.t('settings:knowledgeBases.field.chunkOverlap.placeholder'); },
      min: 0,
      max: 5000,
      get helpText() { return i18n.t('settings:knowledgeBases.field.chunkOverlap.help'); }
    },
    {
      type: 'checkbox',
      name: 'enabled',
      get label() { return i18n.t('settings:knowledgeBases.field.enabled'); },
      defaultValue: true
    }
  ],

  // Edit fields (id is disabled)
  editFields: [
    {
      type: 'text',
      name: 'id',
      get label() { return i18n.t('settings:knowledgeBases.field.id'); },
      required: true,
      disabled: true
    },
    {
      type: 'text',
      name: 'name',
      get label() { return i18n.t('settings:knowledgeBases.field.name'); },
      get placeholder() { return i18n.t('settings:knowledgeBases.field.name.placeholder'); },
      required: true
    },
    {
      type: 'text',
      name: 'description',
      get label() { return i18n.t('settings:knowledgeBases.field.description'); },
      get placeholder() { return i18n.t('settings:knowledgeBases.field.description.placeholder'); },
      get helpText() { return i18n.t('settings:knowledgeBases.field.description.help'); }
    },
    {
      type: 'text',
      name: 'embedding_model',
      get label() { return i18n.t('settings:knowledgeBases.field.embeddingModel'); },
      get placeholder() { return i18n.t('settings:knowledgeBases.field.embeddingModel.placeholder'); },
      get helpText() { return i18n.t('settings:knowledgeBases.field.embeddingModel.help'); }
    },
    {
      type: 'number',
      name: 'chunk_size',
      get label() { return i18n.t('settings:knowledgeBases.field.chunkSize'); },
      get placeholder() { return i18n.t('settings:knowledgeBases.field.chunkSize.placeholder'); },
      min: 100,
      max: 10000,
      get helpText() { return i18n.t('settings:knowledgeBases.field.chunkSize.help'); }
    },
    {
      type: 'number',
      name: 'chunk_overlap',
      get label() { return i18n.t('settings:knowledgeBases.field.chunkOverlap'); },
      get placeholder() { return i18n.t('settings:knowledgeBases.field.chunkOverlap.placeholder'); },
      min: 0,
      max: 5000,
      get helpText() { return i18n.t('settings:knowledgeBases.field.chunkOverlap.help'); }
    },
    {
      type: 'checkbox',
      name: 'enabled',
      get label() { return i18n.t('settings:knowledgeBases.field.enabled'); },
      defaultValue: true
    }
  ],

  // Enable default CRUD actions
  enableDefaultActions: {
    create: true,
    edit: true,
    delete: true,
  }
};
