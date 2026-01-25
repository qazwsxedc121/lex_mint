/**
 * 模型列表管理组件
 */

import React, { useState } from 'react';
import { PlusIcon, PencilIcon, TrashIcon, StarIcon } from '@heroicons/react/24/outline';
import { StarIcon as StarIconSolid } from '@heroicons/react/24/solid';
import type { Model, Provider, DefaultConfig } from '../types/model';

interface ModelListProps {
  models: Model[];
  providers: Provider[];
  defaultConfig: DefaultConfig | null;
  createModel: (model: Model) => Promise<void>;
  updateModel: (modelId: string, model: Model) => Promise<void>;
  deleteModel: (modelId: string) => Promise<void>;
  setDefault: (providerId: string, modelId: string) => Promise<void>;
}

export const ModelList: React.FC<ModelListProps> = ({
  models,
  providers,
  defaultConfig,
  createModel,
  updateModel,
  deleteModel,
  setDefault,
}) => {
  const [showForm, setShowForm] = useState(false);
  const [editingModel, setEditingModel] = useState<Model | null>(null);
  const [filterProvider, setFilterProvider] = useState<string>('');
  const [formData, setFormData] = useState<Model>({
    id: '',
    name: '',
    provider_id: '',
    group: '通用',
    temperature: 0.7,
    enabled: true,
  });

  // 筛选模型
  const filteredModels = filterProvider
    ? models.filter((m) => m.provider_id === filterProvider)
    : models;

  const handleCreate = () => {
    setEditingModel(null);
    setFormData({
      id: '',
      name: '',
      provider_id: providers[0]?.id || '',
      group: '通用',
      temperature: 0.7,
      enabled: true,
    });
    setShowForm(true);
  };

  const handleEdit = (model: Model) => {
    setEditingModel(model);
    setFormData(model);
    setShowForm(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingModel) {
        await updateModel(editingModel.id, formData);
      } else {
        await createModel(formData);
      }
      setShowForm(false);
    } catch (error) {
      alert(error instanceof Error ? error.message : '操作失败');
    }
  };

  const handleDelete = async (modelId: string) => {
    if (!confirm('确定要删除此模型吗？')) return;
    try {
      await deleteModel(modelId);
    } catch (error) {
      alert(error instanceof Error ? error.message : '删除失败');
    }
  };

  const handleSetDefault = async (model: Model) => {
    try {
      await setDefault(model.provider_id, model.id);
    } catch (error) {
      alert(error instanceof Error ? error.message : '设置失败');
    }
  };

  const isDefaultModel = (modelId: string) => defaultConfig?.model === modelId;

  return (
    <div className="space-y-4">
      {/* 头部操作栏 */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <h3 className="text-lg font-medium text-gray-900 dark:text-white">
            模型列表
          </h3>
          <select
            value={filterProvider}
            onChange={(e) => setFilterProvider(e.target.value)}
            className="px-3 py-1 text-sm border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white"
          >
            <option value="">全部提供商</option>
            {providers.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={handleCreate}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
        >
          <PlusIcon className="h-4 w-4" />
          添加模型
        </button>
      </div>

      {/* 模型表格 */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
          <thead className="bg-gray-50 dark:bg-gray-900">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                模型 ID
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                名称
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                提供商
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                分组
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                温度
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
            {filteredModels.map((model) => {
              const provider = providers.find((p) => p.id === model.provider_id);
              return (
                <tr key={model.id}>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-900 dark:text-white">
                        {model.id}
                      </span>
                      {isDefaultModel(model.id) && (
                        <StarIconSolid className="h-4 w-4 text-yellow-400" title="默认模型" />
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {model.name}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {provider?.name || model.provider_id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {model.group}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                    {model.temperature}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                        model.enabled
                          ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                          : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                      }`}
                    >
                      {model.enabled ? '启用' : '禁用'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <button
                      onClick={() => handleSetDefault(model)}
                      disabled={isDefaultModel(model.id)}
                      className="text-yellow-600 hover:text-yellow-900 dark:text-yellow-400 dark:hover:text-yellow-300 mr-3 disabled:opacity-50"
                      title="设为默认"
                    >
                      <StarIcon className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => handleEdit(model)}
                      className="text-blue-600 hover:text-blue-900 dark:text-blue-400 dark:hover:text-blue-300 mr-3"
                    >
                      <PencilIcon className="h-4 w-4" />
                    </button>
                    <button
                      onClick={() => handleDelete(model.id)}
                      disabled={isDefaultModel(model.id)}
                      className="text-red-600 hover:text-red-900 dark:text-red-400 dark:hover:text-red-300 disabled:opacity-50"
                      title={isDefaultModel(model.id) ? '不能删除默认模型' : '删除'}
                    >
                      <TrashIcon className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              );
            })}
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
                {editingModel ? '编辑模型' : '添加模型'}
              </h3>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    模型 ID *
                  </label>
                  <input
                    type="text"
                    required
                    disabled={!!editingModel}
                    value={formData.id}
                    onChange={(e) => setFormData({ ...formData, id: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white disabled:opacity-50"
                    placeholder="例如: gpt-4-turbo"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    模型名称 *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                    placeholder="GPT-4 Turbo"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    所属提供商 *
                  </label>
                  <select
                    required
                    value={formData.provider_id}
                    onChange={(e) => setFormData({ ...formData, provider_id: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                  >
                    <option value="">选择提供商</option>
                    {providers.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    分组名称 *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.group}
                    onChange={(e) => setFormData({ ...formData, group: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                    placeholder="对话模型"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    温度参数: {formData.temperature}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.1"
                    value={formData.temperature}
                    onChange={(e) =>
                      setFormData({ ...formData, temperature: parseFloat(e.target.value) })
                    }
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mt-1">
                    <span>0.0 (精确)</span>
                    <span>1.0 (平衡)</span>
                    <span>2.0 (创造)</span>
                  </div>
                </div>
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="model-enabled"
                    checked={formData.enabled}
                    onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                    className="h-4 w-4 text-blue-600 border-gray-300 rounded"
                  />
                  <label
                    htmlFor="model-enabled"
                    className="ml-2 block text-sm text-gray-700 dark:text-gray-300"
                  >
                    启用此模型
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
                    {editingModel ? '保存' : '创建'}
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
