/**
 * 模型选择器组件
 *
 * 在聊天界面显示当前模型，支持切换
 */

import React, { useState, useEffect } from 'react';
import { ChevronDownIcon } from '@heroicons/react/24/outline';
import { listModels, updateSessionModel } from '../services/api';
import type { Model } from '../types/model';

interface ModelSelectorProps {
  sessionId: string;
  currentModelId?: string;
  onModelChange?: (modelId: string) => void;
}

export const ModelSelector: React.FC<ModelSelectorProps> = ({
  sessionId,
  currentModelId,
  onModelChange,
}) => {
  const [models, setModels] = useState<Model[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  // 加载模型列表
  useEffect(() => {
    const loadModels = async () => {
      try {
        const data = await listModels();
        // 只显示已启用的模型
        setModels(data.filter((m) => m.enabled));
      } catch (error) {
        console.error('Failed to load models:', error);
      } finally {
        setLoading(false);
      }
    };
    loadModels();
  }, []);

  // 当前选中的模型（支持复合ID）
  const currentModel = models.find((m) => {
    const compositeId = `${m.provider_id}:${m.id}`;
    return compositeId === currentModelId || m.id === currentModelId;
  });

  // 按分组整理模型
  const groupedModels = models.reduce((acc, model) => {
    const group = model.group || '通用';
    if (!acc[group]) acc[group] = [];
    acc[group].push(model);
    return acc;
  }, {} as Record<string, Model[]>);

  const handleSelectModel = async (model: Model) => {
    // 构造复合ID: provider_id:model_id
    const compositeId = `${model.provider_id}:${model.id}`;

    if (compositeId === currentModelId) {
      setIsOpen(false);
      return;
    }

    try {
      await updateSessionModel(sessionId, compositeId);
      onModelChange?.(compositeId);
      setIsOpen(false);
    } catch (error) {
      console.error('Failed to update model:', error);
      alert('切换模型失败');
    }
  };

  if (loading) {
    return (
      <div className="text-sm text-gray-500 dark:text-gray-400">
        加载中...
      </div>
    );
  }

  return (
    <div className="relative">
      {/* 当前模型显示按钮 */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 text-sm bg-gray-100 dark:bg-gray-700 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
      >
        <span className="text-gray-700 dark:text-gray-300">
          {currentModel ? currentModel.name : currentModelId || '未知模型'}
        </span>
        <ChevronDownIcon
          className={`h-4 w-4 text-gray-500 transition-transform ${
            isOpen ? 'transform rotate-180' : ''
          }`}
        />
      </button>

      {/* 下拉菜单 */}
      {isOpen && (
        <>
          {/* 遮罩层 */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />

          {/* 菜单内容 */}
          <div className="absolute right-0 mt-2 w-64 bg-white dark:bg-gray-800 rounded-md shadow-lg z-20 border border-gray-200 dark:border-gray-700 max-h-96 overflow-y-auto">
            <div className="py-2">
              {Object.entries(groupedModels).map(([group, groupModels]) => (
                <div key={group}>
                  {/* 分组标题 */}
                  <div className="px-4 py-2 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    {group}
                  </div>

                  {/* 该分组的模型列表 */}
                  {groupModels.map((model) => {
                    const compositeId = `${model.provider_id}:${model.id}`;
                    const isSelected = compositeId === currentModelId || model.id === currentModelId;

                    return (
                      <button
                        key={compositeId}
                        onClick={() => handleSelectModel(model)}
                        className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 ${
                          isSelected
                            ? 'bg-blue-50 dark:bg-blue-900 text-blue-600 dark:text-blue-300'
                            : 'text-gray-700 dark:text-gray-300'
                        }`}
                      >
                        <div className="font-medium">{model.name}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">
                          {model.id}
                        </div>
                      </button>
                    );
                  })}
                </div>
              ))}

              {models.length === 0 && (
                <div className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 text-center">
                  没有可用的模型
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};
