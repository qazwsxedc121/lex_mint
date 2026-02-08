/**
 * Knowledge Bases Page Configuration
 *
 * Defines the structure and behavior of the Knowledge Bases settings page.
 */

import type { CrudSettingsConfig } from './types';
import type { KnowledgeBase } from '../../../types/knowledgeBase';

export const knowledgeBasesConfig: CrudSettingsConfig<KnowledgeBase> = {
  type: 'crud',
  title: 'Knowledge Bases',
  description: 'Manage knowledge bases for RAG (Retrieval-Augmented Generation)',
  itemName: 'knowledge base',
  itemNamePlural: 'knowledge bases',
  createMode: 'page',
  createPath: '/settings/knowledge-bases/new',
  editMode: 'page',
  editPath: (itemId) => `/settings/knowledge-bases/${itemId}`,

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
      key: 'document_count',
      label: 'Documents',
      sortable: true,
      hideOnMobile: true,
      render: (value) => value || 0
    },
    {
      key: 'created_at',
      label: 'Created',
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
  searchPlaceholder: 'Search knowledge bases...',

  // Form fields for create
  createFields: [
    {
      type: 'text',
      name: 'id',
      label: 'Knowledge Base ID',
      placeholder: 'e.g., my-knowledge-base',
      required: true,
      helpText: 'Unique identifier for this knowledge base'
    },
    {
      type: 'text',
      name: 'name',
      label: 'Name',
      placeholder: 'My Knowledge Base',
      required: true
    },
    {
      type: 'text',
      name: 'description',
      label: 'Description',
      placeholder: 'Optional description',
      helpText: 'Brief description of this knowledge base'
    },
    {
      type: 'text',
      name: 'embedding_model',
      label: 'Embedding Model Override',
      placeholder: 'e.g., deepseek:deepseek-chat',
      helpText: 'Override the default embedding model (leave empty to use global RAG config)'
    },
    {
      type: 'number',
      name: 'chunk_size',
      label: 'Chunk Size Override',
      placeholder: 'e.g., 1000',
      min: 100,
      max: 10000,
      helpText: 'Override chunk size for this KB (leave empty to use global RAG config)'
    },
    {
      type: 'number',
      name: 'chunk_overlap',
      label: 'Chunk Overlap Override',
      placeholder: 'e.g., 200',
      min: 0,
      max: 5000,
      helpText: 'Override chunk overlap for this KB (leave empty to use global RAG config)'
    },
    {
      type: 'checkbox',
      name: 'enabled',
      label: 'Enable this knowledge base',
      defaultValue: true
    }
  ],

  // Edit fields (id is disabled)
  editFields: [
    {
      type: 'text',
      name: 'id',
      label: 'Knowledge Base ID',
      required: true,
      disabled: true
    },
    {
      type: 'text',
      name: 'name',
      label: 'Name',
      placeholder: 'My Knowledge Base',
      required: true
    },
    {
      type: 'text',
      name: 'description',
      label: 'Description',
      placeholder: 'Optional description',
      helpText: 'Brief description of this knowledge base'
    },
    {
      type: 'text',
      name: 'embedding_model',
      label: 'Embedding Model Override',
      placeholder: 'e.g., deepseek:deepseek-chat',
      helpText: 'Override the default embedding model (leave empty to use global RAG config)'
    },
    {
      type: 'number',
      name: 'chunk_size',
      label: 'Chunk Size Override',
      placeholder: 'e.g., 1000',
      min: 100,
      max: 10000,
      helpText: 'Override chunk size for this KB (leave empty to use global RAG config)'
    },
    {
      type: 'number',
      name: 'chunk_overlap',
      label: 'Chunk Overlap Override',
      placeholder: 'e.g., 200',
      min: 0,
      max: 5000,
      helpText: 'Override chunk overlap for this KB (leave empty to use global RAG config)'
    },
    {
      type: 'checkbox',
      name: 'enabled',
      label: 'Enable this knowledge base',
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
