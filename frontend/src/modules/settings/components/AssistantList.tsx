/**
 * AssistantList component - CRUD interface for managing assistants
 */

import React, { useState } from 'react';
import { PlusIcon, PencilIcon, TrashIcon, StarIcon } from '@heroicons/react/24/outline';
import { StarIcon as StarIconSolid } from '@heroicons/react/24/solid';
import type { Assistant, AssistantCreate, AssistantUpdate } from '../../../types/assistant';
import type { Model } from '../../../types/model';

interface AssistantListProps {
  assistants: Assistant[];
  defaultAssistantId: string | null;
  models: Model[];
  onCreateAssistant: (assistant: AssistantCreate) => Promise<void>;
  onUpdateAssistant: (id: string, assistant: AssistantUpdate) => Promise<void>;
  onDeleteAssistant: (id: string) => Promise<void>;
  onSetDefault: (id: string) => Promise<void>;
}

export const AssistantList: React.FC<AssistantListProps> = ({
  assistants,
  defaultAssistantId,
  models,
  onCreateAssistant,
  onUpdateAssistant,
  onDeleteAssistant,
  onSetDefault,
}) => {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formData, setFormData] = useState<Partial<AssistantCreate>>({
    enabled: true,
  });

  const handleEdit = (assistant: Assistant) => {
    setEditingId(assistant.id);
    setFormData(assistant);
    setShowCreateForm(false);
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setFormData({ enabled: true });
  };

  const handleSave = async () => {
    try {
      if (editingId) {
        await onUpdateAssistant(editingId, formData as AssistantUpdate);
        setEditingId(null);
      } else {
        if (!formData.id || !formData.name || !formData.model_id) {
          alert('Please fill in required fields: ID, Name, and Model');
          return;
        }
        await onCreateAssistant(formData as AssistantCreate);
        setShowCreateForm(false);
      }
      setFormData({ enabled: true });
    } catch (err) {
      alert(`Failed to save: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this assistant?')) return;
    try {
      await onDeleteAssistant(id);
    } catch (err) {
      alert(`Failed to delete: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  const isDefaultAssistant = (id: string) => defaultAssistantId === id;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium text-gray-900 dark:text-white">
          Assistant List
        </h3>
        <button
          onClick={() => setShowCreateForm(true)}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
        >
          <PlusIcon className="h-4 w-4" />
          Add Assistant
        </button>
      </div>

      {/* Assistants Table */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-900">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Name
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Model
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Temperature
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Max Rounds
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
            {assistants.map((assistant) => (
              <tr key={assistant.id}>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center gap-2">
                    <div>
                      <div className="text-sm font-medium text-gray-900 dark:text-white">
                        {assistant.name}
                      </div>
                      {assistant.description && (
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          {assistant.description}
                        </div>
                      )}
                    </div>
                    {isDefaultAssistant(assistant.id) && (
                      <StarIconSolid className="h-4 w-4 text-yellow-400" title="Default Assistant" />
                    )}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                  {assistant.model_id}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                  {assistant.temperature ?? 'Default'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                  {assistant.max_rounds === -1 ? 'Unlimited' :
                   assistant.max_rounds === null || assistant.max_rounds === undefined ? 'Unlimited' :
                   assistant.max_rounds}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span
                    className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      assistant.enabled
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                        : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                    }`}
                  >
                    {assistant.enabled ? 'Enabled' : 'Disabled'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <button
                    onClick={() => onSetDefault(assistant.id)}
                    disabled={isDefaultAssistant(assistant.id)}
                    className="text-yellow-600 hover:text-yellow-900 dark:text-yellow-400 dark:hover:text-yellow-300 mr-3 disabled:opacity-50"
                    title="Set as default"
                  >
                    <StarIcon className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleEdit(assistant)}
                    className="text-blue-600 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-300 mr-3"
                  >
                    <PencilIcon className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(assistant.id)}
                    disabled={isDefaultAssistant(assistant.id)}
                    className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300 disabled:opacity-50"
                    title={isDefaultAssistant(assistant.id) ? 'Cannot delete default assistant' : 'Delete'}
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create/Edit Modal */}
      {(showCreateForm || editingId) && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div
            className="fixed inset-0 bg-black bg-opacity-50"
            onClick={() => {
              handleCancelEdit();
              setShowCreateForm(false);
            }}
          />
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md p-6">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
                {editingId ? 'Edit Assistant' : 'Add Assistant'}
              </h3>
              <form onSubmit={(e) => { e.preventDefault(); handleSave(); }} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Assistant ID *
                  </label>
                  <input
                    type="text"
                    required
                    disabled={!!editingId}
                    value={formData.id || ''}
                    onChange={(e) => setFormData({ ...formData, id: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white disabled:opacity-50"
                    placeholder="e.g., my-assistant"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.name || ''}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                    placeholder="My Assistant"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Description
                  </label>
                  <input
                    type="text"
                    value={formData.description || ''}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                    placeholder="Optional description"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Model *
                  </label>
                  <select
                    required
                    value={formData.model_id || ''}
                    onChange={(e) => setFormData({ ...formData, model_id: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                  >
                    <option value="">Select a model</option>
                    {models.filter(m => m.enabled).map((model) => (
                      <option key={`${model.provider_id}:${model.id}`} value={`${model.provider_id}:${model.id}`}>
                        {model.name} ({model.provider_id}:{model.id})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    System Prompt
                  </label>
                  <textarea
                    value={formData.system_prompt || ''}
                    onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                    placeholder="Optional system prompt..."
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Temperature: {formData.temperature ?? 'Default'}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.1"
                    value={formData.temperature ?? 0.7}
                    onChange={(e) =>
                      setFormData({ ...formData, temperature: parseFloat(e.target.value) })
                    }
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mt-1">
                    <span>0.0 (Precise)</span>
                    <span>1.0 (Balanced)</span>
                    <span>2.0 (Creative)</span>
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Max Rounds
                  </label>
                  <input
                    type="number"
                    value={formData.max_rounds ?? ''}
                    onChange={(e) => {
                      const val = e.target.value;
                      setFormData({
                        ...formData,
                        max_rounds: val === '' ? undefined : val === '-1' ? -1 : parseInt(val)
                      });
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                    placeholder="-1 for unlimited"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    -1 or empty = unlimited
                  </p>
                </div>
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="assistant-enabled"
                    checked={formData.enabled !== false}
                    onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                    className="h-4 w-4 text-blue-600 border-gray-300 rounded"
                  />
                  <label
                    htmlFor="assistant-enabled"
                    className="ml-2 block text-sm text-gray-700 dark:text-gray-300"
                  >
                    Enable this assistant
                  </label>
                </div>
                <div className="flex justify-end gap-3 mt-6">
                  <button
                    type="button"
                    onClick={() => {
                      handleCancelEdit();
                      setShowCreateForm(false);
                    }}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
                  >
                    {editingId ? 'Save' : 'Create'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
