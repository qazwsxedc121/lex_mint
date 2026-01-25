/**
 * 模型设置模态框 - 主容器
 *
 * 提供模型和提供商配置的可视化界面
 */

import React, { useState } from 'react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { ProviderList } from './ProviderList';
import { ModelList } from './ModelList';
import { useModels } from '../hooks/useModels';

interface ModelSettingsProps {
  isOpen: boolean;
  onClose: () => void;
}

type TabType = 'models' | 'providers';

export const ModelSettings: React.FC<ModelSettingsProps> = ({ isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<TabType>('models');
  const modelsHook = useModels();

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* 背景遮罩 */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
        onClick={onClose}
      />

      {/* 模态框内容 */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col">
          {/* 头部 */}
          <div className="flex items-center justify-between p-6 border-b dark:border-gray-700">
            <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
              模型配置管理
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-500 dark:hover:text-gray-300"
            >
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>

          {/* 标签页 */}
          <div className="border-b dark:border-gray-700">
            <nav className="flex px-6 -mb-px space-x-8">
              <button
                onClick={() => setActiveTab('models')}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'models'
                    ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                }`}
              >
                模型管理
              </button>
              <button
                onClick={() => setActiveTab('providers')}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'providers'
                    ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                }`}
              >
                提供商管理
              </button>
            </nav>
          </div>

          {/* 内容区域 */}
          <div className="flex-1 overflow-y-auto p-6">
            {modelsHook.loading ? (
              <div className="flex items-center justify-center h-64">
                <div className="text-gray-500 dark:text-gray-400">加载中...</div>
              </div>
            ) : modelsHook.error ? (
              <div className="flex items-center justify-center h-64">
                <div className="text-red-500">{modelsHook.error}</div>
              </div>
            ) : (
              <>
                {activeTab === 'models' && <ModelList {...modelsHook} />}
                {activeTab === 'providers' && <ProviderList {...modelsHook} />}
              </>
            )}
          </div>

          {/* 底部 */}
          <div className="flex items-center justify-end gap-3 p-6 border-t dark:border-gray-700">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600"
            >
              关闭
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
