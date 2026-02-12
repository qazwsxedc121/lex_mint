/**
 * CompareModelButton - Toolbar button that opens a model picker for multi-model comparison.
 */

import React, { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { ScaleIcon } from '@heroicons/react/24/outline';
import { listModels, listProviders } from '../../../services/api';

const TOOLBAR_BTN = 'flex items-center justify-center p-1.5 rounded-md border transition-colors disabled:opacity-50 disabled:cursor-not-allowed';

interface CompareModelButtonProps {
  disabled?: boolean;
  isStreaming?: boolean;
  onCompareActivate: (modelIds: string[]) => void;
}

interface ModelOption {
  compositeId: string;
  displayName: string;
  providerName: string;
}

export const CompareModelButton: React.FC<CompareModelButtonProps> = ({
  disabled = false,
  isStreaming = false,
  onCompareActivate,
}) => {
  const { t } = useTranslation('chat');
  const [isOpen, setIsOpen] = useState(false);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [loadingModels, setLoadingModels] = useState(false);
  const popupRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Close popup on outside click
  useEffect(() => {
    if (!isOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (
        popupRef.current && !popupRef.current.contains(e.target as Node) &&
        buttonRef.current && !buttonRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [isOpen]);

  const handleOpen = async () => {
    if (isOpen) {
      setIsOpen(false);
      return;
    }

    setIsOpen(true);
    setSelectedIds(new Set());

    if (models.length === 0) {
      setLoadingModels(true);
      try {
        const [providerList, modelList] = await Promise.all([
          listProviders(),
          listModels(),
        ]);

        const providerMap = new Map(providerList.map(p => [p.id, p.name]));
        const options: ModelOption[] = [];

        for (const model of modelList) {
          if (!model.enabled) continue;
          const providerName = providerMap.get(model.provider_id) || model.provider_id;
          options.push({
            compositeId: `${model.provider_id}:${model.id}`,
            displayName: model.name || model.id,
            providerName,
          });
        }

        setModels(options);
      } catch (err) {
        console.error('Failed to load models:', err);
      } finally {
        setLoadingModels(false);
      }
    }
  };

  const toggleModel = (compositeId: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(compositeId)) {
        next.delete(compositeId);
      } else {
        next.add(compositeId);
      }
      return next;
    });
  };

  const handleConfirm = () => {
    const ids = Array.from(selectedIds);
    if (ids.length >= 2) {
      onCompareActivate(ids);
      setIsOpen(false);
    }
  };

  const handleCancel = () => {
    setIsOpen(false);
    setSelectedIds(new Set());
  };

  // Group models by provider
  const groupedModels = models.reduce<Record<string, ModelOption[]>>((acc, m) => {
    if (!acc[m.providerName]) acc[m.providerName] = [];
    acc[m.providerName].push(m);
    return acc;
  }, {});

  return (
    <div className="relative" data-name="input-box-compare-button">
      <button
        ref={buttonRef}
        type="button"
        onClick={handleOpen}
        disabled={disabled || isStreaming}
        className={`${TOOLBAR_BTN} ${
          isOpen
            ? 'bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800'
            : 'bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-600 hover:bg-purple-50 dark:hover:bg-purple-900/30 hover:text-purple-700 dark:hover:text-purple-300 hover:border-purple-200 dark:hover:border-purple-800'
        } disabled:opacity-50 disabled:cursor-not-allowed`}
        title={t('input.compareModels')}
      >
        <ScaleIcon className="h-4 w-4" />
      </button>

      {isOpen && (
        <div
          ref={popupRef}
          className="absolute left-0 bottom-full mb-2 w-80 bg-white dark:bg-gray-800 rounded-md shadow-lg z-20 border border-gray-200 dark:border-gray-700"
          data-name="compare-model-picker"
        >
          <div className="p-3 border-b border-gray-200 dark:border-gray-700">
            <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
              {t('input.compareSelectModels')}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              {t('input.compareMinModels')}
            </div>
          </div>

          <div className="max-h-64 overflow-auto p-2">
            {loadingModels && (
              <div className="text-sm text-gray-500 dark:text-gray-400 px-2 py-1">
                Loading...
              </div>
            )}
            {!loadingModels && Object.entries(groupedModels).map(([providerName, providerModels]) => (
              <div key={providerName} className="mb-2">
                <div className="text-xs font-medium text-gray-500 dark:text-gray-400 px-2 py-1 uppercase tracking-wide">
                  {providerName}
                </div>
                {providerModels.map(model => (
                  <label
                    key={model.compositeId}
                    className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedIds.has(model.compositeId)}
                      onChange={() => toggleModel(model.compositeId)}
                      className="rounded border-gray-300 dark:border-gray-600 text-purple-600 focus:ring-purple-500"
                    />
                    <span className="text-sm text-gray-900 dark:text-gray-100">
                      {model.displayName}
                    </span>
                  </label>
                ))}
              </div>
            ))}
          </div>

          <div className="flex justify-end gap-2 p-3 border-t border-gray-200 dark:border-gray-700">
            <button
              type="button"
              onClick={handleCancel}
              className="px-3 py-1.5 text-sm text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
            >
              {t('input.compareCancel')}
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={selectedIds.size < 2}
              className="px-3 py-1.5 text-sm text-white bg-purple-600 rounded hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {t('input.compareConfirm')} ({selectedIds.size})
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
