/**
 * SessionTransferModal - Select a target destination for moving/copying sessions.
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { Modal } from '../../../modules/settings/components/common/Modal';
import type { Project } from '../../../types/project';

interface SessionTransferModalProps {
  isOpen: boolean;
  mode: 'move' | 'copy';
  projects: Project[];
  loading: boolean;
  error: string | null;
  busy?: boolean;
  showChatOption?: boolean;
  excludeProjectId?: string | null;
  onClose: () => void;
  onSelectTarget: (targetContextType: 'chat' | 'project', targetProjectId?: string) => void;
  onRetry?: () => void;
}

export const SessionTransferModal: React.FC<SessionTransferModalProps> = ({
  isOpen,
  mode,
  projects,
  loading,
  error,
  busy = false,
  showChatOption = false,
  excludeProjectId,
  onClose,
  onSelectTarget,
  onRetry,
}) => {
  const { t } = useTranslation('chat');
  const filteredProjects = projects.filter((project) => project.id !== excludeProjectId);
  const title = mode === 'move' ? t('transfer.moveConversation') : t('transfer.copyConversation');

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} size="md">
      <div data-name="session-transfer-modal" className="space-y-4">
        <p className="text-sm text-gray-600 dark:text-gray-300">
          {t('transfer.chooseDestination')}
        </p>

        {loading && (
          <div data-name="session-transfer-loading" className="text-sm text-gray-500 dark:text-gray-400">
            {t('transfer.loadingProjects')}
          </div>
        )}

        {error && !loading && (
          <div data-name="session-transfer-error" className="space-y-2">
            <div className="text-sm text-red-600 dark:text-red-400">
              {error}
            </div>
            {onRetry && (
              <button
                onClick={onRetry}
                className="px-3 py-1.5 text-sm font-medium text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300"
              >
                {t('common:retry')}
              </button>
            )}
          </div>
        )}

        {!loading && !error && (
          <div data-name="session-transfer-options" className="space-y-3">
            {showChatOption && (
              <button
                onClick={() => onSelectTarget('chat')}
                disabled={busy}
                className="w-full text-left px-3 py-2 rounded-md border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white hover:bg-gray-100 dark:hover:bg-gray-600 disabled:opacity-60"
              >
                {t('transfer.chatGlobal')}
              </button>
            )}

            <div data-name="session-transfer-projects" className="space-y-2">
              <div className="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
                {t('transfer.projects')}
              </div>
              {filteredProjects.length === 0 ? (
                <div className="text-sm text-gray-500 dark:text-gray-400">
                  {t('transfer.noProjects')}
                </div>
              ) : (
                filteredProjects.map((project) => (
                  <button
                    key={project.id}
                    onClick={() => onSelectTarget('project', project.id)}
                    disabled={busy}
                    className="w-full text-left px-3 py-2 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-60"
                  >
                    <div className="font-medium truncate">{project.name}</div>
                    {project.description && (
                      <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                        {project.description}
                      </div>
                    )}
                  </button>
                ))
              )}
            </div>
          </div>
        )}

        <div data-name="session-transfer-actions" className="flex justify-end gap-2 pt-2">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-sm font-medium text-gray-600 dark:text-gray-300 hover:text-gray-800 dark:hover:text-white"
          >
            {t('common:cancel')}
          </button>
        </div>
      </div>
    </Modal>
  );
};
