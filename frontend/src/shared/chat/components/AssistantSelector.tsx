/**
 * Chat target selector component.
 *
 * Lets users switch between assistant and direct-model chat targets.
 */

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDownIcon, CpuChipIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline';
import { useChatServices } from '../services/ChatServiceProvider';
import type { Assistant } from '../../../types/assistant';
import type { Model } from '../../../types/model';
import { listModels } from '../../../services/api';
import { getAssistantIcon } from '../../constants/assistantIcons';
import { useTranslation } from 'react-i18next';

interface AssistantSelectorProps {
  sessionId: string;
  currentAssistantId?: string;
  currentModelId?: string;
  currentTargetType?: 'assistant' | 'model';
  onTargetChange?: (target: { targetType: 'assistant' | 'model'; targetId: string; modelId?: string }) => void;
}

export const AssistantSelector: React.FC<AssistantSelectorProps> = ({
  sessionId,
  currentAssistantId,
  currentModelId,
  currentTargetType = 'model',
  onTargetChange,
}) => {
  const { api } = useChatServices();
  const { t } = useTranslation('chat');
  const [assistants, setAssistants] = useState<Assistant[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'model' | 'assistant'>('model');
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0, width: 0 });

  useEffect(() => {
    const loadData = async () => {
      try {
        const [assistantList, modelList] = await Promise.all([
          api.listAssistants(),
          listModels(),
        ]);
        setAssistants(assistantList.filter((item) => item.enabled));
        setModels(modelList.filter((item) => item.enabled));
      } catch (error) {
        console.error('Failed to load target selector data:', error);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [api]);

  useEffect(() => {
    setActiveTab(currentTargetType === 'assistant' ? 'assistant' : 'model');
  }, [currentTargetType]);

  useEffect(() => {
    if (!isOpen || !buttonRef.current) return;
    const rect = buttonRef.current.getBoundingClientRect();
    setDropdownPosition({
      top: rect.top,
      left: rect.left,
      width: rect.width,
    });
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) {
      setSearchTerm('');
    }
  }, [isOpen]);

  const currentAssistant = assistants.find((item) => item.id === currentAssistantId);
  const currentModel = models.find((item) => `${item.provider_id}:${item.id}` === currentModelId);
  const currentLabel = currentTargetType === 'assistant'
    ? (currentAssistant?.name || t('selector.assistantDefaultLabel'))
    : (currentModel?.name || currentModelId || t('selector.modelDefaultLabel'));

  const normalizedSearchTerm = searchTerm.trim().toLowerCase();

  const filteredAssistants = useMemo(() => {
    if (!normalizedSearchTerm) {
      return assistants;
    }

    return assistants.filter((assistant) => {
      const haystack = `${assistant.name} ${assistant.id} ${assistant.model_id} ${assistant.description || ''}`.toLowerCase();
      return haystack.includes(normalizedSearchTerm);
    });
  }, [assistants, normalizedSearchTerm]);

  const filteredModels = useMemo(() => {
    if (!normalizedSearchTerm) {
      return models;
    }

    return models.filter((model) => {
      const compositeModelId = `${model.provider_id}:${model.id}`;
      const haystack = `${model.name} ${compositeModelId}`.toLowerCase();
      return haystack.includes(normalizedSearchTerm);
    });
  }, [models, normalizedSearchTerm]);

  const handleSelectAssistant = async (assistant: Assistant) => {
    try {
      await api.updateSessionTarget(sessionId, 'assistant', { assistantId: assistant.id });
      onTargetChange?.({
        targetType: 'assistant',
        targetId: assistant.id,
        modelId: assistant.model_id,
      });
      setIsOpen(false);
    } catch (error) {
      console.error('Failed to switch assistant:', error);
      alert(t('selector.switchFailed'));
    }
  };

  const handleSelectModel = async (model: Model) => {
    const compositeModelId = `${model.provider_id}:${model.id}`;
    try {
      await api.updateSessionTarget(sessionId, 'model', { modelId: compositeModelId });
      onTargetChange?.({
        targetType: 'model',
        targetId: compositeModelId,
      });
      setIsOpen(false);
    } catch (error) {
      console.error('Failed to switch model target:', error);
      alert(t('selector.switchFailed'));
    }
  };

  if (loading) {
    return <div className="text-sm text-gray-500 dark:text-gray-400">{t('selector.loading')}</div>;
  }

  const ToolbarIcon = currentTargetType === 'assistant'
    ? getAssistantIcon(currentAssistant?.icon)
    : CpuChipIcon;

  return (
    <div data-name="assistant-selector-root">
      <button
        ref={buttonRef}
        onClick={() => setIsOpen((prev) => !prev)}
        className="flex items-center gap-1.5 p-1.5 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-md hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors border border-blue-200 dark:border-blue-800"
        title={currentLabel}
      >
        <ToolbarIcon className="w-4 h-4" />
        <ChevronDownIcon className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && createPortal(
        <>
          <div className="fixed inset-0 z-[100]" onClick={() => setIsOpen(false)} />
          <div
            data-name="assistant-selector-dropdown"
            className="fixed bg-white dark:bg-gray-800 rounded-md shadow-lg z-[101] border border-gray-200 dark:border-gray-700 max-h-96 overflow-y-auto"
            style={{
              top: `${dropdownPosition.top - 8}px`,
              left: `${dropdownPosition.left}px`,
              width: '360px',
              transform: 'translateY(-100%)',
            }}
          >
            <div className="px-2 pt-2">
              <div className="flex rounded-md bg-gray-100 dark:bg-gray-700 p-1">
                <button
                  type="button"
                  onClick={() => setActiveTab('model')}
                  className={`flex-1 rounded px-2 py-1 text-xs font-medium ${
                    activeTab === 'model'
                      ? 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100'
                      : 'text-gray-600 dark:text-gray-300'
                  }`}
                >
                  {t('selector.modelsTab')}
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('assistant')}
                  className={`flex-1 rounded px-2 py-1 text-xs font-medium ${
                    activeTab === 'assistant'
                      ? 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100'
                      : 'text-gray-600 dark:text-gray-300'
                  }`}
                >
                  {t('selector.assistantsTab')}
                </button>
              </div>
              <div className="relative mt-2 mb-1">
                <MagnifyingGlassIcon className="pointer-events-none absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400 dark:text-gray-500" />
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  placeholder={activeTab === 'assistant' ? t('selector.searchAssistants') : t('selector.searchModels')}
                  className="w-full rounded-md border border-gray-200 bg-white py-1.5 pl-8 pr-2 text-xs text-gray-800 outline-none focus:border-blue-400 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
                />
              </div>
            </div>

            <div className="py-2">
              {activeTab === 'assistant' ? (
                filteredAssistants.map((assistant) => {
                  const isSelected = currentTargetType === 'assistant' && assistant.id === currentAssistantId;
                  const ItemIcon = getAssistantIcon(assistant.icon);
                  return (
                    <button
                      key={assistant.id}
                      onClick={() => void handleSelectAssistant(assistant)}
                      className={`w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${
                        isSelected ? 'bg-blue-50 dark:bg-blue-900/30 border-l-4 border-blue-500' : ''
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <ItemIcon className="w-4 h-4 shrink-0 text-gray-500 dark:text-gray-400" />
                        <span className={`text-sm font-medium shrink-0 ${isSelected ? 'text-blue-600 dark:text-blue-300' : 'text-gray-900 dark:text-gray-100'}`}>
                          {assistant.name}
                        </span>
                        <span className="text-xs text-gray-400 dark:text-gray-500 truncate ml-auto max-w-[140px]" title={assistant.model_id}>
                          {assistant.model_id}
                        </span>
                      </div>
                    </button>
                  );
                })
              ) : (
                filteredModels.map((model) => {
                  const compositeModelId = `${model.provider_id}:${model.id}`;
                  const isSelected = currentTargetType === 'model' && compositeModelId === currentModelId;
                  return (
                    <button
                      key={compositeModelId}
                      onClick={() => void handleSelectModel(model)}
                      className={`w-full text-left px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${
                        isSelected ? 'bg-blue-50 dark:bg-blue-900/30 border-l-4 border-blue-500' : ''
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <CpuChipIcon className="w-4 h-4 shrink-0 text-gray-500 dark:text-gray-400" />
                        <span className={`text-sm font-medium shrink-0 ${isSelected ? 'text-blue-600 dark:text-blue-300' : 'text-gray-900 dark:text-gray-100'}`}>
                          {model.name}
                        </span>
                        <span className="text-xs text-gray-400 dark:text-gray-500 truncate ml-auto max-w-[170px]" title={compositeModelId}>
                          {compositeModelId}
                        </span>
                      </div>
                    </button>
                  );
                })
              )}

              {activeTab === 'assistant' && filteredAssistants.length === 0 && (
                <div className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 text-center">
                  {normalizedSearchTerm ? t('selector.noMatchingAssistants') : t('selector.noAssistantsAvailable')}
                </div>
              )}
              {activeTab === 'model' && filteredModels.length === 0 && (
                <div className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400 text-center">
                  {normalizedSearchTerm ? t('selector.noMatchingModels') : t('selector.noModelsAvailable')}
                </div>
              )}
            </div>
          </div>
        </>,
        document.body
      )}
    </div>
  );
};
