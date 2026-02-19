/**
 * GroupChatCreateModal - Modal for creating group chat sessions.
 * Supports assistant and direct-model participants.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowDownIcon, ArrowUpIcon, XMarkIcon } from '@heroicons/react/24/outline';
import type { Assistant } from '../../../types/assistant';
import type { Model } from '../../../types/model';
import type { GroupChatMode } from '../../../types/message';
import { listModels } from '../../../services/api';
import { useChatServices } from '../services/ChatServiceProvider';

interface GroupChatCreateModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: (sessionId: string) => void;
}

const MODEL_PARTICIPANT_PREFIX = 'model::';

function extractErrorDetail(error: unknown): string | null {
  if (!error || typeof error !== 'object') {
    return error instanceof Error ? error.message : null;
  }

  const payload = error as { response?: { data?: { detail?: unknown } }; message?: string };
  const detail = payload.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string };
    if (first && typeof first.msg === 'string' && first.msg.trim()) {
      return first.msg;
    }
  }
  return typeof payload.message === 'string' && payload.message.trim() ? payload.message : null;
}

export const GroupChatCreateModal: React.FC<GroupChatCreateModalProps> = ({
  open,
  onClose,
  onCreated,
}) => {
  const { t } = useTranslation('chat');
  const { api } = useChatServices();
  const [assistants, setAssistants] = useState<Assistant[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [selectedParticipantIds, setSelectedParticipantIds] = useState<string[]>([]);
  const [groupMode, setGroupMode] = useState<GroupChatMode>('round_robin');
  const [loading, setLoading] = useState(false);
  const [toastError, setToastError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setSelectedParticipantIds([]);
    setGroupMode('round_robin');
    setToastError(null);
    Promise.all([api.listAssistants(), listModels()])
      .then(([assistantList, modelList]) => {
        setAssistants(assistantList.filter((item) => item.enabled));
        setModels(modelList.filter((item) => item.enabled));
      })
      .catch((err: unknown) => {
        const detail = extractErrorDetail(err);
        setAssistants([]);
        setModels([]);
        setToastError(
          detail
            ? t('groupChat.loadAssistantsFailedWithDetail', { error: detail })
            : t('groupChat.loadAssistantsFailed')
        );
      });
  }, [open, api, t]);

  useEffect(() => {
    if (!toastError) return;
    const timer = window.setTimeout(() => setToastError(null), 3600);
    return () => window.clearTimeout(timer);
  }, [toastError]);

  const participantNameMap = useMemo(() => {
    const map = new Map<string, string>();
    assistants.forEach((assistant) => map.set(assistant.id, assistant.name));
    models.forEach((model) => map.set(`${MODEL_PARTICIPANT_PREFIX}${model.provider_id}:${model.id}`, model.name || `${model.provider_id}:${model.id}`));
    return map;
  }, [assistants, models]);

  const toggle = (participantId: string) => {
    setSelectedParticipantIds((prev) => {
      if (prev.includes(participantId)) {
        return prev.filter((id) => id !== participantId);
      }
      return [...prev, participantId];
    });
  };

  const moveSelectedParticipant = (participantId: string, direction: 'up' | 'down') => {
    setSelectedParticipantIds((prev) => {
      const currentIndex = prev.indexOf(participantId);
      if (currentIndex < 0) return prev;
      const nextIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1;
      if (nextIndex < 0 || nextIndex >= prev.length) return prev;
      const next = [...prev];
      const [movedParticipantId] = next.splice(currentIndex, 1);
      next.splice(nextIndex, 0, movedParticipantId);
      return next;
    });
  };

  const handleCreate = async () => {
    if (selectedParticipantIds.length < 2) return;
    setLoading(true);
    try {
      const sessionId = await api.createGroupSession(selectedParticipantIds, groupMode);
      onCreated(sessionId);
      onClose();
    } catch (err: unknown) {
      const detail = extractErrorDetail(err);
      setToastError(
        detail
          ? t('groupChat.createFailedWithDetail', { error: detail })
          : t('groupChat.createFailed')
      );
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div
      data-name="group-chat-modal-backdrop"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      {toastError && (
        <div
          data-name="group-chat-modal-toast-error"
          className="absolute top-4 left-1/2 -translate-x-1/2 max-w-xl rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 shadow-md dark:border-red-700 dark:bg-red-900/70 dark:text-red-100"
        >
          {toastError}
        </div>
      )}
      <div
        data-name="group-chat-modal"
        className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">
            {t('groupChat.createTitle')}
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        <div className="px-4 py-3 max-h-80 overflow-y-auto">
          <div className="mb-3 space-y-2">
            <p className="text-xs font-medium text-gray-600 dark:text-gray-300">
              {t('groupChat.modeLabel')}
            </p>
            <div className="grid grid-cols-1 gap-2">
              <label className="flex cursor-pointer items-start gap-2 rounded-md border border-gray-200 px-2.5 py-2 text-xs hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700/30">
                <input
                  type="radio"
                  name="group-chat-mode"
                  value="round_robin"
                  checked={groupMode === 'round_robin'}
                  onChange={() => setGroupMode('round_robin')}
                  className="mt-0.5"
                />
                <div className="min-w-0">
                  <div className="font-medium text-gray-800 dark:text-gray-100">{t('groupChat.modeRoundRobin')}</div>
                  <div className="text-[11px] text-gray-500 dark:text-gray-400">{t('groupChat.modeRoundRobinHint')}</div>
                </div>
              </label>
              <label className="flex cursor-pointer items-start gap-2 rounded-md border border-gray-200 px-2.5 py-2 text-xs hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-700/30">
                <input
                  type="radio"
                  name="group-chat-mode"
                  value="committee"
                  checked={groupMode === 'committee'}
                  onChange={() => setGroupMode('committee')}
                  className="mt-0.5"
                />
                <div className="min-w-0">
                  <div className="font-medium text-gray-800 dark:text-gray-100">{t('groupChat.modeCommittee')}</div>
                  <div className="text-[11px] text-gray-500 dark:text-gray-400">{t('groupChat.modeCommitteeHint')}</div>
                </div>
              </label>
            </div>
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
            {t('groupChat.selectHint')}
          </p>

          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Assistants</p>
            {assistants.map((assistant) => (
              <label
                key={assistant.id}
                className="flex items-center gap-3 px-3 py-2 rounded-md cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700"
              >
                <input
                  type="checkbox"
                  checked={selectedParticipantIds.includes(assistant.id)}
                  onChange={() => toggle(assistant.id)}
                  className="rounded border-gray-300 dark:border-gray-600 text-blue-500 focus:ring-blue-500"
                />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                    {assistant.name}
                  </div>
                  {assistant.description && (
                    <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                      {assistant.description}
                    </div>
                  )}
                </div>
              </label>
            ))}

            <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Models</p>
            {models.map((model) => {
              const participantId = `${MODEL_PARTICIPANT_PREFIX}${model.provider_id}:${model.id}`;
              return (
                <label
                  key={participantId}
                  className="flex items-center gap-3 px-3 py-2 rounded-md cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700"
                >
                  <input
                    type="checkbox"
                    checked={selectedParticipantIds.includes(participantId)}
                    onChange={() => toggle(participantId)}
                    className="rounded border-gray-300 dark:border-gray-600 text-blue-500 focus:ring-blue-500"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                      {model.name}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                      {model.provider_id}:{model.id}
                    </div>
                  </div>
                </label>
              );
            })}
          </div>

          {assistants.length === 0 && models.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-4">
              {t('groupChat.noAssistants')}
            </p>
          )}

          {groupMode === 'round_robin' && selectedParticipantIds.length > 0 && (
            <div className="mt-4 rounded-md border border-gray-200 p-2.5 dark:border-gray-700">
              <p className="mb-2 text-xs font-medium text-gray-600 dark:text-gray-300">
                {t('groupChat.createOrderTitle')}
              </p>
              <div className="space-y-1.5">
                {selectedParticipantIds.map((participantId, index) => {
                  const participantName = participantNameMap.get(participantId) || `AI-${participantId.slice(0, 4)}`;
                  return (
                    <div
                      key={participantId}
                      className="flex items-center justify-between rounded-md border border-gray-200 bg-gray-50 px-2 py-1.5 text-xs dark:border-gray-700 dark:bg-gray-900/40"
                    >
                      <div className="min-w-0">
                        <span className="mr-1 text-gray-400 dark:text-gray-500">#{index + 1}</span>
                        <span className="truncate text-gray-700 dark:text-gray-200">{participantName}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => moveSelectedParticipant(participantId, 'up')}
                          disabled={index === 0}
                          className="rounded border border-gray-300 p-0.5 text-gray-500 hover:bg-gray-100 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-40"
                          title={t('groupChat.moveUp')}
                        >
                          <ArrowUpIcon className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => moveSelectedParticipant(participantId, 'down')}
                          disabled={index === selectedParticipantIds.length - 1}
                          className="rounded border border-gray-300 p-0.5 text-gray-500 hover:bg-gray-100 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-40"
                          title={t('groupChat.moveDown')}
                        >
                          <ArrowDownIcon className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 px-4 py-3 border-t border-gray-200 dark:border-gray-700">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200"
          >
            {t('common:cancel')}
          </button>
          <button
            onClick={handleCreate}
            disabled={selectedParticipantIds.length < 2 || loading}
            className="px-3 py-1.5 text-sm bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? '...' : t('groupChat.create')}
          </button>
        </div>
      </div>
    </div>
  );
};
