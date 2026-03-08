import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { SparklesIcon, FolderOpenIcon, TrashIcon } from '@heroicons/react/24/outline';
import { useTranslation } from 'react-i18next';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { addProjectWorkspaceItem } from '../../services/api';
import { ChatComposerProvider, ChatServiceProvider, type ChatNavigation, useChatComposer, useChatServices } from '../../shared/chat';
import { useProjectWorkspaceStore } from '../../stores/projectWorkspaceStore';
import type { ProjectWorkspaceOutletContext } from './workspace';
import { getProjectWorkspacePath } from './workspace';
import { createProjectChatAPI } from './services/projectChatAPI';
import ProjectChatSidebar from './components/ProjectChatSidebar';
import { getAgentContextOriginLabel } from './agentContext';

const EMPTY_CONTEXT_ITEMS: Array<{
  id: string;
  title: string;
  content: string;
  kind?: 'context' | 'note';
  language?: string;
  source?: {
    filePath: string;
    startLine: number;
    endLine: number;
  };
  origin: 'file' | 'search' | 'workflow';
  createdAt: number;
}> = [];

interface ProjectAgentWorkspaceContentProps {
  projectId: string;
  currentSessionId: string | null;
  onSetCurrentSessionId: (sessionId: string | null) => void;
}

const ProjectAgentWorkspaceContent: React.FC<ProjectAgentWorkspaceContentProps> = ({
  projectId,
  currentSessionId,
  onSetCurrentSessionId,
}) => {
  const { t } = useTranslation('projects');
  const navigate = useNavigate();
  const chatComposer = useChatComposer();
  const { createSession } = useChatServices();
  const agentContextItems = useProjectWorkspaceStore((state) => state.agentContextMap[projectId] || EMPTY_CONTEXT_ITEMS);
  const consumePendingAgentContext = useProjectWorkspaceStore((state) => state.consumePendingAgentContext);
  const clearAgentContextItems = useProjectWorkspaceStore((state) => state.clearAgentContextItems);
  const currentFilePath = useProjectWorkspaceStore((state) => state.projectFileMap[projectId] || null);

  useEffect(() => {
    if (!chatComposer.isReady) {
      return;
    }

    const pendingItems = consumePendingAgentContext(projectId);
    if (pendingItems.length === 0) {
      return;
    }

    let cancelled = false;

    const hydrateComposer = async () => {
      let sessionId = currentSessionId;
      if (!sessionId) {
        sessionId = await createSession();
        if (cancelled) {
          return;
        }
        onSetCurrentSessionId(sessionId);
        void addProjectWorkspaceItem(projectId, {
          type: 'session',
          id: sessionId,
          title: t('session.defaultTitle'),
          meta: {
            message_count: 0,
          },
        }).catch((error) => {
          console.error('Failed to persist new agent session:', error);
        });
      }

      for (const item of pendingItems) {
        await chatComposer.addBlock({
          title: item.title,
          content: item.content,
          collapsed: true,
          kind: item.kind || 'context',
          language: item.language,
          source: item.source,
        });
      }

      await chatComposer.focus();
    };

    void hydrateComposer().catch((error) => {
      console.error('Failed to hydrate Agent composer context:', error);
    });

    return () => {
      cancelled = true;
    };
  }, [chatComposer, chatComposer.isReady, consumePendingAgentContext, createSession, currentSessionId, onSetCurrentSessionId, projectId, t]);

  const handleAttachContextItem = useCallback(async (item: typeof agentContextItems[number]) => {
    await chatComposer.addBlock({
      title: item.title,
      content: item.content,
      collapsed: true,
      kind: item.kind || 'context',
      language: item.language,
      source: item.source,
    });
    await chatComposer.focus();
  }, [chatComposer]);

  return (
    <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <ProjectChatSidebar
          projectId={projectId}
          currentSessionId={currentSessionId}
          savedSessionId={currentSessionId}
          onSetCurrentSessionId={onSetCurrentSessionId}
        />
      </div>

      <aside className="min-h-0 overflow-y-auto rounded-2xl border border-gray-200 bg-white/95 p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900/95">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{t('workspace.agent.contextTitle')}</h3>
          {agentContextItems.length > 0 && (
            <button
              type="button"
              onClick={() => clearAgentContextItems(projectId)}
              className="inline-flex items-center gap-1 rounded-lg border border-gray-300 px-2 py-1 text-xs text-gray-600 hover:bg-gray-100 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
              data-name="project-agent-clear-context"
            >
              <TrashIcon className="h-3.5 w-3.5" />
              {t('workspace.agent.clearContext')}
            </button>
          )}
        </div>

        <div className="mt-4 space-y-3">
          <div className="rounded-xl border border-blue-200 bg-blue-50/70 p-3 dark:border-blue-900/40 dark:bg-blue-950/20">
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-blue-700 dark:text-blue-300">
              {t('workspace.agent.activeFileTitle')}
            </div>
            <div className="mt-2 text-sm text-gray-700 dark:text-gray-200 break-words">
              {currentFilePath || t('workspace.agent.noActiveFile')}
            </div>
            {currentFilePath && (
              <button
                type="button"
                onClick={() => navigate(getProjectWorkspacePath(projectId, 'files'))}
                className="mt-3 inline-flex items-center gap-1 rounded-lg border border-blue-200 bg-white px-2.5 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-50 dark:border-blue-800 dark:bg-blue-950/30 dark:text-blue-200 dark:hover:bg-blue-950/50"
                data-name="project-agent-open-active-file"
              >
                <FolderOpenIcon className="h-3.5 w-3.5" />
                {t('workspace.agent.openFiles')}
              </button>
            )}
          </div>

          {agentContextItems.length === 0 ? (
            <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 px-3 py-4 text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-950/40 dark:text-gray-400">
              {t('workspace.agent.contextEmpty')}
            </div>
          ) : (
            agentContextItems.map((item) => (
              <section
                key={item.id}
                className="rounded-xl border border-gray-200 bg-gray-50/80 p-3 dark:border-gray-800 dark:bg-gray-950/40"
                data-name="project-agent-context-item"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-gray-500 dark:text-gray-400">
                      {getAgentContextOriginLabel(item.origin)}
                    </div>
                    <div className="mt-1 text-sm font-medium text-gray-900 dark:text-gray-100 break-words">{item.title}</div>
                  </div>
                </div>
                <div className="mt-2 line-clamp-6 whitespace-pre-wrap break-words text-xs text-gray-600 dark:text-gray-300">
                  {item.content}
                </div>
                <button
                  type="button"
                  onClick={() => void handleAttachContextItem(item)}
                  className="mt-3 rounded-lg border border-gray-300 px-2.5 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-100 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                  data-name="project-agent-attach-context"
                >
                  {t('workspace.agent.attachContext')}
                </button>
              </section>
            ))
          )}

          <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-3 text-xs text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200">
            {t('workspace.agent.patchHint')}
          </div>
        </div>
      </aside>
    </div>
  );
};

export const ProjectAgentView: React.FC = () => {
  const { t } = useTranslation('projects');
  const { projectId, currentProject } = useOutletContext<ProjectWorkspaceOutletContext>();
  const savedAgentSessionId = useProjectWorkspaceStore((state) => state.agentSessionMap[projectId] || null);
  const currentFilePath = useProjectWorkspaceStore((state) => state.projectFileMap[projectId] || null);
  const setAgentSession = useProjectWorkspaceStore((state) => state.setAgentSession);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(savedAgentSessionId);

  useEffect(() => {
    setCurrentSessionId(savedAgentSessionId);
  }, [savedAgentSessionId]);

  const handleSetCurrentSessionId = useCallback((sessionId: string | null) => {
    setCurrentSessionId(sessionId);
    setAgentSession(projectId, sessionId);
  }, [projectId, setAgentSession]);

  const projectChatAPI = useMemo(() => {
    return createProjectChatAPI(projectId, {
      getActiveDocumentContext: () => ({
        activeFilePath: currentFilePath || undefined,
      }),
    });
  }, [currentFilePath, projectId]);

  const navigation = useMemo<ChatNavigation>(() => ({
    navigateToSession: (sessionId: string) => handleSetCurrentSessionId(sessionId),
    navigateToRoot: () => {
      // No-op: Agent is already page scoped.
    },
    getCurrentSessionId: () => currentSessionId,
  }), [currentSessionId, handleSetCurrentSessionId]);

  return (
    <ChatServiceProvider api={projectChatAPI} navigation={navigation}>
      <ChatComposerProvider>
        <div data-name="project-agent-view" className="flex h-full min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden bg-gray-50 px-4 py-4 dark:bg-gray-950">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-gray-200 bg-white px-4 py-3 dark:border-gray-800 dark:bg-gray-900">
            <div className="flex min-w-0 items-start gap-3">
              <div className="rounded-xl bg-blue-50 p-2 text-blue-700 dark:bg-blue-900/30 dark:text-blue-200">
                <SparklesIcon className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{t('workspace.agent.title')}</h2>
                <p className="mt-0.5 text-sm text-gray-600 dark:text-gray-300">
                  {t('workspace.agent.description', { projectName: currentProject?.name || 'project' })}
                </p>
              </div>
            </div>
            {currentProject && (
              <div className="inline-flex items-center rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 dark:border-blue-800 dark:bg-blue-900/20 dark:text-blue-200">
                {currentProject.name}
              </div>
            )}
          </div>

          <ProjectAgentWorkspaceContent
            projectId={projectId}
            currentSessionId={currentSessionId}
            onSetCurrentSessionId={handleSetCurrentSessionId}
          />
        </div>
      </ChatComposerProvider>
    </ChatServiceProvider>
  );
};
