/**
 * Provider list management component
 *
 * Supports:
 * - Builtin providers (DeepSeek, OpenAI, OpenRouter, etc.)
 * - Custom providers with protocol selection
 * - Model capabilities display
 */

import React, { useState, useEffect } from 'react';
import { PlusIcon, PencilIcon, TrashIcon, CheckCircleIcon, CloudArrowDownIcon } from '@heroicons/react/24/outline';
import type { Provider, BuiltinProviderInfo, ApiProtocol } from '../../../types/model';
import {
  getProvider,
  testProviderConnection,
  testProviderStoredConnection,
  listBuiltinProviders,
  listProtocols,
} from '../../../services/api';

interface ProviderListProps {
  providers: Provider[];
  createProvider: (provider: Provider) => Promise<void>;
  updateProvider: (providerId: string, provider: Provider) => Promise<void>;
  deleteProvider: (providerId: string) => Promise<void>;
}

interface ProtocolOption {
  id: ApiProtocol;
  name: string;
  description: string;
}

export const ProviderList: React.FC<ProviderListProps> = ({
  providers,
  createProvider,
  updateProvider,
  deleteProvider,
}) => {
  const [showForm, setShowForm] = useState(false);
  const [showBuiltinPicker, setShowBuiltinPicker] = useState(false);
  const [editingProvider, setEditingProvider] = useState<Provider | null>(null);
  const [builtinProviders, setBuiltinProviders] = useState<BuiltinProviderInfo[]>([]);
  const [protocols, setProtocols] = useState<ProtocolOption[]>([]);
  const [formData, setFormData] = useState<Provider>({
    id: '',
    name: '',
    base_url: '',
    api_key_env: '',
    api_key: '',
    enabled: true,
    type: 'custom',
    protocol: 'openai',
  });
  const [testStatus, setTestStatus] = useState<{
    loading: boolean;
    success?: boolean;
    message?: string;
  }>({ loading: false });
  const [testModelId, setTestModelId] = useState<string>('gpt-3.5-turbo');

  // Load builtin providers and protocols on mount
  useEffect(() => {
    const loadData = async () => {
      try {
        const [builtins, protocolList] = await Promise.all([
          listBuiltinProviders(),
          listProtocols(),
        ]);
        setBuiltinProviders(builtins);
        setProtocols(protocolList);
      } catch (error) {
        console.error('Failed to load builtin providers:', error);
      }
    };
    loadData();
  }, []);

  // Check if a builtin provider is already configured
  const isBuiltinConfigured = (builtinId: string) => {
    return providers.some(p => p.id === builtinId);
  };

  const handleAddBuiltin = (builtin: BuiltinProviderInfo) => {
    setEditingProvider(null);
    setFormData({
      id: builtin.id,
      name: builtin.name,
      base_url: builtin.base_url,
      api_key_env: builtin.api_key_env,
      api_key: '',
      enabled: true,
      type: 'builtin',
      protocol: builtin.protocol as ApiProtocol,
      sdk_class: builtin.sdk_class,
      default_capabilities: builtin.default_capabilities,
    });
    setTestStatus({ loading: false });
    setTestModelId(builtin.builtin_models[0]?.id || 'gpt-3.5-turbo');
    setShowBuiltinPicker(false);
    setShowForm(true);
  };

  const handleCreateCustom = () => {
    setEditingProvider(null);
    setFormData({
      id: '',
      name: '',
      base_url: '',
      api_key_env: '',
      api_key: '',
      enabled: true,
      type: 'custom',
      protocol: 'openai',
    });
    setTestStatus({ loading: false });
    setTestModelId('gpt-3.5-turbo');
    setShowBuiltinPicker(false);
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
    // Check builtin providers first
    const builtin = builtinProviders.find(b => b.id === providerId);
    if (builtin && builtin.builtin_models.length > 0) {
      return builtin.builtin_models[0].id;
    }

    const lowerProviderId = providerId.toLowerCase();
    if (lowerProviderId.includes('deepseek')) {
      return 'deepseek-chat';
    } else if (lowerProviderId.includes('openai')) {
      return 'gpt-3.5-turbo';
    } else if (lowerProviderId.includes('anthropic') || lowerProviderId.includes('claude')) {
      return 'claude-3-haiku-20240307';
    } else if (lowerProviderId.includes('gemini') || lowerProviderId.includes('google')) {
      return 'gemini-pro';
    } else if (lowerProviderId.includes('openrouter')) {
      return 'openai/gpt-3.5-turbo';
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
        <div className="flex gap-2">
          <button
            onClick={() => setShowBuiltinPicker(true)}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-blue-600 bg-blue-50 border border-blue-200 rounded-md hover:bg-blue-100 dark:bg-blue-900/20 dark:border-blue-800 dark:text-blue-400 dark:hover:bg-blue-900/30"
          >
            <CloudArrowDownIcon className="h-4 w-4" />
            Add Builtin
          </button>
          <button
            onClick={handleCreateCustom}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
          >
            <PlusIcon className="h-4 w-4" />
            Add Custom
          </button>
        </div>
      </div>

      {/* Provider Table */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-900">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Provider
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                Type
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                API URL
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                API Key
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
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex flex-col">
                    <span className="text-sm font-medium text-gray-900 dark:text-white">
                      {provider.name}
                    </span>
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      {provider.id}
                    </span>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span
                    className={`px-2 py-1 text-xs rounded-full ${
                      provider.type === 'builtin'
                        ? 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
                        : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                    }`}
                  >
                    {provider.type || 'builtin'}
                  </span>
                  {provider.protocol && (
                    <span className="ml-1 text-xs text-gray-500 dark:text-gray-400">
                      ({provider.protocol})
                    </span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                  <span className="max-w-xs truncate block" title={provider.base_url}>
                    {provider.base_url}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {provider.has_api_key ? (
                    <span className="flex items-center text-green-600 dark:text-green-400">
                      <CheckCircleIcon className="h-4 w-4 mr-1" />
                      <span className="text-xs">Configured</span>
                    </span>
                  ) : (
                    <span className="text-xs text-yellow-600 dark:text-yellow-400">
                      Not set
                    </span>
                  )}
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
                    title="Edit"
                  >
                    <PencilIcon className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(provider.id)}
                    className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300"
                    title="Delete"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
            {providers.length === 0 && (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-gray-500 dark:text-gray-400">
                  No providers configured. Click "Add Builtin" to add a pre-configured provider.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Builtin Provider Picker Modal */}
      {showBuiltinPicker && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div
            className="fixed inset-0 bg-black bg-opacity-50"
            onClick={() => setShowBuiltinPicker(false)}
          />
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl p-6">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
                Add Builtin Provider
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                Select a pre-configured provider. You only need to add your API key.
              </p>
              <div className="grid grid-cols-2 gap-4 max-h-96 overflow-y-auto">
                {builtinProviders.map((builtin) => {
                  const isConfigured = isBuiltinConfigured(builtin.id);
                  return (
                    <div
                      key={builtin.id}
                      className={`p-4 border rounded-lg ${
                        isConfigured
                          ? 'border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900 opacity-60'
                          : 'border-gray-200 hover:border-blue-500 hover:bg-blue-50 dark:border-gray-700 dark:hover:border-blue-500 dark:hover:bg-blue-900/20 cursor-pointer'
                      }`}
                      onClick={() => !isConfigured && handleAddBuiltin(builtin)}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <h4 className="font-medium text-gray-900 dark:text-white">
                            {builtin.name}
                          </h4>
                          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                            Protocol: {builtin.protocol}
                          </p>
                          {builtin.builtin_models.length > 0 && (
                            <p className="text-xs text-gray-500 dark:text-gray-400">
                              Models: {builtin.builtin_models.map(m => m.id).slice(0, 2).join(', ')}
                              {builtin.builtin_models.length > 2 && '...'}
                            </p>
                          )}
                        </div>
                        {isConfigured && (
                          <span className="text-xs text-green-600 dark:text-green-400 flex items-center">
                            <CheckCircleIcon className="h-4 w-4 mr-1" />
                            Added
                          </span>
                        )}
                      </div>
                      {/* Capabilities badges */}
                      <div className="flex flex-wrap gap-1 mt-2">
                        {builtin.default_capabilities.reasoning && (
                          <span className="px-1.5 py-0.5 text-xs bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300 rounded">
                            Reasoning
                          </span>
                        )}
                        {builtin.default_capabilities.vision && (
                          <span className="px-1.5 py-0.5 text-xs bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 rounded">
                            Vision
                          </span>
                        )}
                        {builtin.default_capabilities.function_calling && (
                          <span className="px-1.5 py-0.5 text-xs bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300 rounded">
                            Functions
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="flex justify-end mt-6">
                <button
                  type="button"
                  onClick={() => setShowBuiltinPicker(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

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
                {editingProvider ? 'Edit Provider' : formData.type === 'builtin' ? `Add ${formData.name}` : 'Add Custom Provider'}
              </h3>
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Provider ID - only editable for custom providers */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Provider ID *
                  </label>
                  <input
                    type="text"
                    required
                    disabled={!!editingProvider || formData.type === 'builtin'}
                    value={formData.id}
                    onChange={(e) => setFormData({ ...formData, id: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white disabled:opacity-50"
                    placeholder="e.g., my-custom-provider"
                  />
                </div>

                {/* Display Name */}
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
                    placeholder="e.g., My Provider"
                  />
                </div>

                {/* Protocol - only for custom providers */}
                {formData.type === 'custom' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      API Protocol *
                    </label>
                    <select
                      value={formData.protocol || 'openai'}
                      onChange={(e) => setFormData({ ...formData, protocol: e.target.value as ApiProtocol })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                    >
                      {protocols.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      Most providers use OpenAI-compatible API
                    </p>
                  </div>
                )}

                {/* API Base URL */}
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
                    placeholder="https://api.example.com/v1"
                  />
                </div>

                {/* API Key */}
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
                    placeholder={editingProvider ? "Enter new key to update" : "sk-..."}
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
                    placeholder="e.g., gpt-3.5-turbo"
                  />

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

                {/* Enable checkbox */}
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

                {/* Buttons */}
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
                    {editingProvider ? 'Save' : 'Add Provider'}
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
