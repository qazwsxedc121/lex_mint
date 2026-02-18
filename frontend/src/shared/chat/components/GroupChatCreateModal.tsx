/**
 * GroupChatCreateModal - Modal for creating a group chat session.
 * Lists enabled assistants with checkboxes; requires min 2 to create.
 */

import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { XMarkIcon } from '@heroicons/react/24/outline';
import type { Assistant } from '../../../types/assistant';
import { useChatServices } from '../services/ChatServiceProvider';

interface GroupChatCreateModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: (sessionId: string) => void;
}

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
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [toastError, setToastError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setSelected(new Set());
    setToastError(null);
    api.listAssistants()
      .then(list => {
        setAssistants(list.filter(a => a.enabled));
      })
      .catch((err: unknown) => {
        const detail = extractErrorDetail(err);
        setAssistants([]);
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

  const toggle = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleCreate = async () => {
    if (selected.size < 2) return;
    setLoading(true);
    try {
      const sessionId = await api.createGroupSession(
        Array.from(selected)
      );
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
        onClick={e => e.stopPropagation()}
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
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
            {t('groupChat.selectHint')}
          </p>
          {assistants.map(a => (
            <label
              key={a.id}
              className="flex items-center gap-3 px-3 py-2 rounded-md cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700"
            >
              <input
                type="checkbox"
                checked={selected.has(a.id)}
                onChange={() => toggle(a.id)}
                className="rounded border-gray-300 dark:border-gray-600 text-blue-500 focus:ring-blue-500"
              />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                  {a.name}
                </div>
                {a.description && (
                  <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                    {a.description}
                  </div>
                )}
              </div>
            </label>
          ))}
          {assistants.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-4">
              {t('groupChat.noAssistants')}
            </p>
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
            disabled={selected.size < 2 || loading}
            className="px-3 py-1.5 text-sm bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? '...' : t('groupChat.create')}
          </button>
        </div>
      </div>
    </div>
  );
};
