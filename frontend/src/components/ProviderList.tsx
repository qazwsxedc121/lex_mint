/**
 * 提供商列表管理组件
 */

import React, { useState } from 'react';
import { PlusIcon, PencilIcon, TrashIcon } from '@heroicons/react/24/outline';
import type { Provider } from '../types/model';

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
    enabled: true,
  });

  const handleCreate = () => {
    setEditingProvider(null);
    setFormData({
      id: '',
      name: '',
      base_url: '',
      api_key_env: '',
      enabled: true,
    });
    setShowForm(true);
  };

  const handleEdit = (provider: Provider) => {
    setEditingProvider(provider);
    setFormData(provider);
    setShowForm(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingProvider) {
        await updateProvider(editingProvider.id, formData);
      } else {
        await createProvider(formData);
      }
      setShowForm(false);
    } catch (error) {
      alert(error instanceof Error ? error.message : '操作失败');
    }
  };

  const handleDelete = async (providerId: string) => {
    if (!confirm('确定要删除此提供商吗？关联的模型也将被删除。')) return;
    try {
      await deleteProvider(providerId);
    } catch (error) {
      alert(error instanceof Error ? error.message : '删除失败');
    }
  };

  return (
    <div className="space-y-4">
      {/* 头部操作栏 */}
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium text-gray-900 dark:text-white">
          LLM 提供商列表
        </h3>
        <button
          onClick={handleCreate}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
        >
          <PlusIcon className="h-4 w-4" />
          添加提供商
        </button>
      </div>

      {/* 提供商表格 */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-900">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                ID
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                名称
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                API 地址
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                环境变量
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                状态
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                操作
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
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                  {provider.api_key_env}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span
                    className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      provider.enabled
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                        : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                    }`}
                  >
                    {provider.enabled ? '启用' : '禁用'}
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

      {/* 创建/编辑表单模态框 */}
      {showForm && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div
            className="fixed inset-0 bg-black bg-opacity-50"
            onClick={() => setShowForm(false)}
          />
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md p-6">
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
                {editingProvider ? '编辑提供商' : '添加提供商'}
              </h3>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    提供商 ID *
                  </label>
                  <input
                    type="text"
                    required
                    disabled={!!editingProvider}
                    value={formData.id}
                    onChange={(e) => setFormData({ ...formData, id: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white disabled:opacity-50"
                    placeholder="例如: openai"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    显示名称 *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                    placeholder="例如: OpenAI"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    API 基础 URL *
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
                    API 密钥环境变量 *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.api_key_env}
                    onChange={(e) =>
                      setFormData({ ...formData, api_key_env: e.target.value })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                    placeholder="OPENAI_API_KEY"
                  />
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
                    启用此提供商
                  </label>
                </div>
                <div className="flex justify-end gap-3 mt-6">
                  <button
                    type="button"
                    onClick={() => setShowForm(false)}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600"
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
                  >
                    {editingProvider ? '保存' : '创建'}
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
