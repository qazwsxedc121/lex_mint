/**
 * Provider list management component
 */

import React, { useState } from 'react';
import { PlusIcon, PencilIcon, TrashIcon } from '@heroicons/react/24/outline';
import type { Provider } from '../../../types/model';
import { getProvider, testProviderConnection, testProviderStoredConnection } from '../../../services/api';

interface ProviderListProps {
  providers: Provider[];
  createProvider: (provider: Provider) => Promise<void>;
  updateProvider: (providerId: string, provider: Provider) => Promise<void>;
  deleteProvider: (providerId: string) => Promise<void>;
}

export const ProviderList: React.FC<ProviderListProps> = ({
  providers,
  createProvider,
  updateProvider,
  deleteProvider,
}) => {
  const [showForm, setShowForm] = useState(false);
  const [editingProvider, setEditingProvider] = useState<Provider | null>(null);
  const [formData, setFormData] = useState<Provider>({
    id: '',
    name: '',
    base_url: '',
    api_key_env: '',
    api_key: '',
    enabled: true,
  });
  const [testStatus, setTestStatus] = useState<{
    loading: boolean;
    success?: boolean;
    message?: string;
  }>({ loading: false });
  const [testModelId, setTestModelId] = useState<string>('gpt-3.5-turbo');

  const handleCreate = () => {
    setEditingProvider(null);
    setFormData({
      id: '',
      name: '',
      base_url: '',
      api_key_env: '',
      api_key: '',
      enabled: true,
    });
    setTestStatus({ loading: false });
    setTestModelId('gpt-3.5-turbo');
    setShowForm(true);
  };

  const handleEdit = async (provider: Provider) => {
    setEditingProvider(provider);
    try {
      const providerWithMaskedKey = await getProvider(provider.id, true);
      setFormData({
        ...providerWithMaskedKey,
        api_key: providerWithMaskedKey.api_key || '',
      });
      setTestStatus({ loading: false });
      const defaultModel = getDefaultModelForProvider(provider.id);
      setTestModelId(defaultModel);
      setShowForm(true);
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Failed to load provider details');
    }
  };

  const getDefaultModelForProvider = (providerId: string): string => {
    const lowerProviderId = providerId.toLowerCase();
    if (lowerProviderId.includes('deepseek')) {
      return 'deepseek-chat';
    } else if (lowerProviderId.includes('openai')) {
      return 'gpt-3.5-turbo';
    } else if (lowerProviderId.includes('anthropic') || lowerProviderId.includes('claude')) {
      return 'claude-3-haiku-20240307';
    } else if (lowerProviderId.includes('gemini') || lowerProviderId.includes('google')) {
      return 'gemini-pro';
    } else {
      return 'gpt-3.5-turbo';
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingProvider) {
        const updateData = { ...formData };
        if (!updateData.api_key || updateData.api_key.includes('****')) {
          delete updateData.api_key;
        }
        await updateProvider(editingProvider.id, updateData);
      } else {
        await createProvider(formData);
      }
      setShowForm(false);
      setTestStatus({ loading: false });
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Operation failed');
    }
  };

  const handleTestConnection = async () => {
    if (!formData.base_url) {
      setTestStatus({
        loading: false,
        success: false,
        message: 'Please fill in API URL first',
      });
      return;
    }

    if (!testModelId.trim()) {
      setTestStatus({
        loading: false,
        success: false,
        message: 'Please fill in Test Model ID',
      });
      return;
    }

    setTestStatus({ loading: true });

    try {
      let result;

      if (editingProvider && formData.api_key && formData.api_key.includes('****')) {
        result = await testProviderStoredConnection(
          editingProvider.id,
          formData.base_url,
          testModelId
        );
      } else {
        if (!formData.api_key) {
          setTestStatus({
            loading: false,
            success: false,
            message: 'Please fill in API Key first',
          });
          return;
        }

        result = await testProviderConnection(
          formData.base_url,
          formData.api_key,
          testModelId
        );
      }

      setTestStatus({
        loading: false,
        success: result.success,
        message: result.message,
      });
    } catch (error) {
      setTestStatus({
        loading: false,
        success: false,
        message: error instanceof Error ? error.message : 'Test failed',
      });
    }
  };

  const handleDelete = async (providerId: string) => {
    if (!confirm('Are you sure you want to delete this provider? Associated models will also be deleted.')) return;
    try {
      await deleteProvider(providerId);
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Delete failed');
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium text-gray-900 dark:text-white">
          LLM Provider List
        </h3>
        <button
          onClick={handleCreate}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
        >
          <PlusIcon className="h-4 w-4" />
          Add Provider
        </button>
      </div>

      {/* Provider Table */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-900">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                ID
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Name
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                API URL
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
            {providers.map((provider) => (
              <tr key={provider.id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                  {provider.id}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                  {provider.name}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                  {provider.base_url}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span
                    className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      provider.enabled
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                        : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                    }`}
                  >
                    {provider.enabled ? 'Enabled' : 'Disabled'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <button
                    onClick={() => handleEdit(provider)}
                    className="text-blue-600 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-300 mr-4"
                  >
                    <PencilIcon className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(provider.id)}
                    className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create/Edit Form Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div
            className="fixed inset-0 bg-black bg-opacity-50"
            onClick={() => setShowForm(false)}
          />
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md p-6">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
                {editingProvider ? 'Edit Provider' : 'Add Provider'}
              </h3>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Provider ID *
                  </label>
                  <input
                    type="text"
                    required
                    disabled={!!editingProvider}
                    value={formData.id}
                    onChange={(e) => setFormData({ ...formData, id: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white disabled:opacity-50"
                    placeholder="e.g., openai"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Display Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                    placeholder="e.g., OpenAI"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    API Base URL *
                  </label>
                  <input
                    type="url"
                    required
                    value={formData.base_url}
                    onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                    placeholder="https://api.openai.com/v1"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    API Key {!editingProvider && '*'}
                  </label>
                  <input
                    type="password"
                    required={!editingProvider}
                    value={formData.api_key || ''}
                    onChange={(e) => {
                      setFormData({ ...formData, api_key: e.target.value });
                      setTestStatus({ loading: false });
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                    placeholder={editingProvider ? "Enter new key to update (leave blank to keep current)" : "sk-..."}
                  />
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    {editingProvider
                      ? "Leave blank to keep current key"
                      : "Key will be stored securely"}
                  </p>
                </div>

                {/* Test Model ID */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Test Model ID
                  </label>
                  <input
                    type="text"
                    value={testModelId}
                    onChange={(e) => setTestModelId(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                    placeholder="e.g., gpt-3.5-turbo, deepseek-chat"
                  />
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    Model ID to use for testing (e.g., gpt-3.5-turbo for OpenAI, deepseek-chat for DeepSeek)
                  </p>

                  {/* Test button */}
                  <button
                    type="button"
                    onClick={handleTestConnection}
                    disabled={
                      testStatus.loading ||
                      !formData.base_url ||
                      !testModelId.trim() ||
                      (!formData.api_key && !editingProvider)
                    }
                    className="mt-2 w-full px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 border border-gray-300 rounded-md hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {testStatus.loading ? 'Testing...' : 'Test Connection'}
                  </button>

                  {/* Test result */}
                  {testStatus.message && (
                    <div
                      className={`mt-2 px-3 py-2 text-sm rounded-md ${
                        testStatus.success
                          ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                          : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                      }`}
                    >
                      {testStatus.message}
                    </div>
                  )}
                </div>
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="enabled"
                    checked={formData.enabled}
                    onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                    className="h-4 w-4 text-blue-600 border-gray-300 rounded"
                  />
                  <label
                    htmlFor="enabled"
                    className="ml-2 block text-sm text-gray-700 dark:text-gray-300"
                  >
                    Enable this provider
                  </label>
                </div>
                <div className="flex justify-end gap-3 mt-6">
                  <button
                    type="button"
                    onClick={() => setShowForm(false)}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
                  >
                    {editingProvider ? 'Save' : 'Create'}
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
