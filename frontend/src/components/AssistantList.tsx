/**
 * AssistantList component - CRUD interface for managing assistants
 */

import React, { useState } from 'react';
import type { Assistant, AssistantCreate, AssistantUpdate } from '../types/assistant';
import type { Model } from '../types/model';

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
        // Update existing
        await onUpdateAssistant(editingId, formData as AssistantUpdate);
        setEditingId(null);
      } else {
        // Create new
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

  return (
    <div className="space-y-4">
      {/* Create button */}
      {!showCreateForm && !editingId && (
        <button
          onClick={() => setShowCreateForm(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
        >
          Create New Assistant
        </button>
      )}

      {/* Create/Edit Form */}
      {(showCreateForm || editingId) && (
        <div className="bg-gray-50 dark:bg-gray-800 p-4 rounded-md border border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-semibold mb-4">
            {editingId ? 'Edit Assistant' : 'Create Assistant'}
          </h3>
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium mb-1">ID *</label>
              <input
                type="text"
                value={formData.id || ''}
                onChange={(e) => setFormData({ ...formData, id: e.target.value })}
                disabled={!!editingId}
                className="w-full px-3 py-2 border rounded-md dark:bg-gray-700 dark:border-gray-600"
                placeholder="e.g., my-assistant"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Name *</label>
              <input
                type="text"
                value={formData.name || ''}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 border rounded-md dark:bg-gray-700 dark:border-gray-600"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Description</label>
              <input
                type="text"
                value={formData.description || ''}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full px-3 py-2 border rounded-md dark:bg-gray-700 dark:border-gray-600"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Model *</label>
              <select
                value={formData.model_id || ''}
                onChange={(e) => setFormData({ ...formData, model_id: e.target.value })}
                className="w-full px-3 py-2 border rounded-md dark:bg-gray-700 dark:border-gray-600"
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
              <label className="block text-sm font-medium mb-1">System Prompt</label>
              <textarea
                value={formData.system_prompt || ''}
                onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
                rows={4}
                className="w-full px-3 py-2 border rounded-md dark:bg-gray-700 dark:border-gray-600"
                placeholder="Optional system prompt..."
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Temperature (0-2)</label>
              <input
                type="number"
                step="0.1"
                min="0"
                max="2"
                value={formData.temperature !== undefined ? formData.temperature : ''}
                onChange={(e) => setFormData({ ...formData, temperature: e.target.value ? parseFloat(e.target.value) : undefined })}
                className="w-full px-3 py-2 border rounded-md dark:bg-gray-700 dark:border-gray-600"
                placeholder="Leave empty for model default"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Max Rounds</label>
              <input
                type="number"
                value={formData.max_rounds || ''}
                onChange={(e) => {
                  const val = e.target.value;
                  setFormData({
                    ...formData,
                    max_rounds: val === '' ? undefined : val === '-1' ? -1 : parseInt(val)
                  });
                }}
                className="w-full px-3 py-2 border rounded-md dark:bg-gray-700 dark:border-gray-600"
                placeholder="-1 for unlimited, or number of rounds"
              />
              <p className="text-xs text-gray-500 mt-1">
                Conversation rounds to keep. -1 or empty = unlimited
              </p>
            </div>
            <div className="flex items-center">
              <input
                type="checkbox"
                checked={formData.enabled !== false}
                onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                className="mr-2"
              />
              <label className="text-sm">Enabled</label>
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <button
              onClick={handleSave}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
            >
              Save
            </button>
            <button
              onClick={() => {
                handleCancelEdit();
                setShowCreateForm(false);
              }}
              className="px-4 py-2 bg-gray-300 dark:bg-gray-600 rounded-md hover:bg-gray-400 dark:hover:bg-gray-500"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Assistants Table */}
      <div className="border border-gray-200 dark:border-gray-700 rounded-md overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-100 dark:bg-gray-800">
            <tr>
              <th className="px-4 py-2 text-left text-sm font-medium">Name</th>
              <th className="px-4 py-2 text-left text-sm font-medium">Model</th>
              <th className="px-4 py-2 text-left text-sm font-medium">Temp</th>
              <th className="px-4 py-2 text-left text-sm font-medium">Rounds</th>
              <th className="px-4 py-2 text-left text-sm font-medium">Status</th>
              <th className="px-4 py-2 text-right text-sm font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {assistants.map((assistant) => (
              <tr key={assistant.id} className="border-t border-gray-200 dark:border-gray-700">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    {assistant.id === defaultAssistantId && (
                      <span className="text-yellow-500" title="Default">★</span>
                    )}
                    <div>
                      <div className="font-medium">{assistant.name}</div>
                      {assistant.description && (
                        <div className="text-xs text-gray-500">{assistant.description}</div>
                      )}
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 text-sm">{assistant.model_id}</td>
                <td className="px-4 py-3 text-sm">{assistant.temperature ?? 'Default'}</td>
                <td className="px-4 py-3 text-sm">
                  {assistant.max_rounds === -1 ? 'Unlimited' :
                   assistant.max_rounds === null || assistant.max_rounds === undefined ? 'Unlimited' :
                   assistant.max_rounds}
                </td>
                <td className="px-4 py-3 text-sm">
                  <span className={`px-2 py-1 rounded text-xs ${
                    assistant.enabled
                      ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                      : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                  }`}>
                    {assistant.enabled ? 'Enabled' : 'Disabled'}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex gap-2 justify-end">
                    {assistant.id !== defaultAssistantId && (
                      <button
                        onClick={() => onSetDefault(assistant.id)}
                        className="text-xs px-2 py-1 bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 rounded hover:bg-yellow-200 dark:hover:bg-yellow-800"
                        title="Set as default"
                      >
                        Set Default
                      </button>
                    )}
                    <button
                      onClick={() => handleEdit(assistant)}
                      className="text-xs px-2 py-1 bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded hover:bg-blue-200 dark:hover:bg-blue-800"
                    >
                      Edit
                    </button>
                    {assistant.id !== defaultAssistantId && (
                      <button
                        onClick={() => handleDelete(assistant.id)}
                        className="text-xs px-2 py-1 bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200 rounded hover:bg-red-200 dark:hover:bg-red-800"
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
