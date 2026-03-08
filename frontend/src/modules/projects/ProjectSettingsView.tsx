import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowPathIcon,
  BookOpenIcon,
  ChatBubbleLeftRightIcon,
  Cog6ToothIcon,
  TrashIcon,
  WrenchScrewdriverIcon,
} from '@heroicons/react/24/outline';
import { useTranslation } from 'react-i18next';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { deleteSession, getToolCatalog, listKnowledgeBases, listSessions, updateProject } from '../../services/api';
import { useProjectWorkspaceStore } from '../../stores/projectWorkspaceStore';
import type { KnowledgeBase } from '../../types/knowledgeBase';
import type { ProjectSettings, ProjectToolCatalogGroup, ProjectToolCatalogItem } from '../../types/project';
import type { ProjectWorkspaceOutletContext } from './workspace';

type FeedbackState =
  | { type: 'success'; message: string }
  | { type: 'error'; message: string }
  | null;

const DEFAULT_PROJECT_SETTINGS: ProjectSettings = {
  rag: {
    knowledge_base_ids: [],
    knowledge_base_mode: 'append',
  },
  tools: {
    tool_enabled_map: {},
  },
};

const buildDefaultToolEnabledMap = (tools: ProjectToolCatalogItem[]): Record<string, boolean> => {
  const defaults: Record<string, boolean> = {};
  for (const tool of tools) {
    defaults[tool.name] = Boolean(tool.enabled_by_default);
  }
  return defaults;
};

const normalizeToolEnabledMap = (
  defaultToolEnabledMap: Record<string, boolean>,
  value?: Record<string, boolean> | null,
): Record<string, boolean> => {
  const merged = { ...defaultToolEnabledMap };
  if (!value) {
    return merged;
  }

  for (const [toolKey, enabled] of Object.entries(value)) {
    if (!toolKey) {
      continue;
    }
    merged[toolKey] = Boolean(enabled);
  }
  return merged;
};

const normalizeProjectSettings = (
  defaultToolEnabledMap: Record<string, boolean>,
  settings?: ProjectSettings | null,
): ProjectSettings => ({
  rag: {
    knowledge_base_ids: settings?.rag?.knowledge_base_ids || [],
    knowledge_base_mode: settings?.rag?.knowledge_base_mode || 'append',
  },
  tools: {
    tool_enabled_map: normalizeToolEnabledMap(defaultToolEnabledMap, settings?.tools?.tool_enabled_map),
  },
});

const areToolMapsEqual = (
  toolDefinitions: ProjectToolCatalogItem[],
  left: Record<string, boolean>,
  right: Record<string, boolean>,
): boolean => {
  for (const definition of toolDefinitions) {
    if (Boolean(left[definition.name]) !== Boolean(right[definition.name])) {
      return false;
    }
  }
  return true;
};

const renderFeedback = (feedback: FeedbackState, dataName: string) => {
  if (!feedback) {
    return null;
  }

  return (
    <div
      className={`mt-4 rounded-xl border px-3 py-2 text-sm ${
        feedback.type === 'success'
          ? 'border-green-200 bg-green-50 text-green-700 dark:border-green-900/50 dark:bg-green-950/20 dark:text-green-300'
          : 'border-red-200 bg-red-50 text-red-700 dark:border-red-900/50 dark:bg-red-950/20 dark:text-red-300'
      }`}
      data-name={dataName}
    >
      {feedback.message}
    </div>
  );
};

export const ProjectSettingsView: React.FC = () => {
  const { t } = useTranslation('projects');
  const navigate = useNavigate();
  const { projectId, currentProject, refreshProjects } = useOutletContext<ProjectWorkspaceOutletContext>();
  const setProjectSession = useProjectWorkspaceStore((state) => state.setProjectSession);
  const setAgentSession = useProjectWorkspaceStore((state) => state.setAgentSession);
  const clearAgentContextItems = useProjectWorkspaceStore((state) => state.clearAgentContextItems);
  const [sessionCount, setSessionCount] = useState<number>(0);
  const [loadingCount, setLoadingCount] = useState(true);
  const [deleting, setDeleting] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<FeedbackState>(null);
  const [knowledgeBaseFeedback, setKnowledgeBaseFeedback] = useState<FeedbackState>(null);
  const [toolFeedback, setToolFeedback] = useState<FeedbackState>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [loadingKnowledgeBases, setLoadingKnowledgeBases] = useState(true);
  const [savingKnowledgeBases, setSavingKnowledgeBases] = useState(false);
  const [savingTools, setSavingTools] = useState(false);
  const [knowledgeBaseLoadError, setKnowledgeBaseLoadError] = useState<string | null>(null);
  const [toolCatalogGroups, setToolCatalogGroups] = useState<ProjectToolCatalogGroup[]>([]);
  const [toolCatalogItems, setToolCatalogItems] = useState<ProjectToolCatalogItem[]>([]);
  const [loadingToolCatalog, setLoadingToolCatalog] = useState(true);
  const [toolCatalogLoadError, setToolCatalogLoadError] = useState<string | null>(null);
  const [draftSettings, setDraftSettings] = useState<ProjectSettings>(DEFAULT_PROJECT_SETTINGS);

  const defaultToolEnabledMap = useMemo(
    () => buildDefaultToolEnabledMap(toolCatalogItems),
    [toolCatalogItems]
  );

  const currentSettings = useMemo(
    () => normalizeProjectSettings(defaultToolEnabledMap, currentProject?.settings),
    [currentProject?.settings, defaultToolEnabledMap]
  );

  useEffect(() => {
    setDraftSettings(currentSettings);
  }, [currentSettings]);

  const loadSessionCount = useCallback(async () => {
    setLoadingCount(true);
    setLoadError(null);
    try {
      const sessions = await listSessions('project', projectId);
      setSessionCount(sessions.length);
    } catch (error) {
      console.error('Failed to load project session count:', error);
      setLoadError(t('workspace.settings.chatHistoryCountFailed'));
    } finally {
      setLoadingCount(false);
    }
  }, [projectId, t]);

  const loadKnowledgeBaseOptions = useCallback(async () => {
    setLoadingKnowledgeBases(true);
    setKnowledgeBaseLoadError(null);
    try {
      const items = await listKnowledgeBases();
      setKnowledgeBases(items.filter((item) => item.enabled));
    } catch (error) {
      console.error('Failed to load project knowledge bases:', error);
      setKnowledgeBaseLoadError(t('workspace.settings.knowledgeBasesLoadFailed'));
    } finally {
      setLoadingKnowledgeBases(false);
    }
  }, [t]);

  const loadToolCatalog = useCallback(async () => {
    setLoadingToolCatalog(true);
    setToolCatalogLoadError(null);
    try {
      const catalog = await getToolCatalog();
      setToolCatalogGroups(catalog.groups || []);
      setToolCatalogItems(catalog.tools || []);
    } catch (error) {
      console.error('Failed to load tool catalog:', error);
      setToolCatalogLoadError(t('workspace.settings.toolsLoadFailed'));
    } finally {
      setLoadingToolCatalog(false);
    }
  }, [t]);

  useEffect(() => {
    void loadSessionCount();
  }, [loadSessionCount]);

  useEffect(() => {
    void loadKnowledgeBaseOptions();
  }, [loadKnowledgeBaseOptions]);

  useEffect(() => {
    void loadToolCatalog();
  }, [loadToolCatalog]);

  const persistProjectSettings = useCallback(async (nextSettings: ProjectSettings) => {
    await updateProject(projectId, { settings: nextSettings });
    await refreshProjects();
  }, [projectId, refreshProjects]);

  const handleDeleteAllConversations = useCallback(async () => {
    const confirmed = window.confirm(
      t('workspace.settings.deleteAllConversationsConfirm', {
        count: sessionCount,
        projectName: currentProject?.name || projectId,
      })
    );

    if (!confirmed) {
      return;
    }

    setDeleting(true);
    setFeedback(null);

    try {
      const sessions = await listSessions('project', projectId);
      for (const session of sessions) {
        await deleteSession(session.session_id, 'project', projectId);
      }

      setProjectSession(projectId, null);
      setAgentSession(projectId, null);
      clearAgentContextItems(projectId);
      setSessionCount(0);
      setFeedback({
        type: 'success',
        message: t('workspace.settings.deleteAllConversationsSuccess', { count: sessions.length }),
      });
      await loadSessionCount();
    } catch (error) {
      console.error('Failed to delete project conversations:', error);
      setFeedback({
        type: 'error',
        message: t('workspace.settings.deleteAllConversationsFailed'),
      });
    } finally {
      setDeleting(false);
    }
  }, [clearAgentContextItems, currentProject?.name, loadSessionCount, projectId, sessionCount, setAgentSession, setProjectSession, t]);

  const knowledgeBaseSelection = draftSettings.rag.knowledge_base_ids;
  const enabledKnowledgeBaseIds = useMemo(() => new Set(knowledgeBases.map((item) => item.id)), [knowledgeBases]);
  const normalizedSelection = useMemo(
    () => knowledgeBaseSelection.filter((kbId) => enabledKnowledgeBaseIds.has(kbId)),
    [enabledKnowledgeBaseIds, knowledgeBaseSelection]
  );
  const isKnowledgeBaseDirty =
    currentSettings.rag.knowledge_base_mode !== draftSettings.rag.knowledge_base_mode
    || currentSettings.rag.knowledge_base_ids.join('|') !== normalizedSelection.join('|');
  const knowledgeToolsDefinitelyUnavailable =
    draftSettings.rag.knowledge_base_mode === 'override' && normalizedSelection.length === 0;
  const isToolDirty = !areToolMapsEqual(toolCatalogItems, currentSettings.tools.tool_enabled_map, draftSettings.tools.tool_enabled_map);
  const groupedToolDefinitions = useMemo(
    () => toolCatalogGroups,
    [toolCatalogGroups]
  );

  useEffect(() => {
    if (knowledgeBaseSelection.length !== normalizedSelection.length) {
      setDraftSettings((prev) => ({
        ...prev,
        rag: {
          ...prev.rag,
          knowledge_base_ids: normalizedSelection,
        },
      }));
    }
  }, [knowledgeBaseSelection, normalizedSelection]);

  const toggleKnowledgeBase = useCallback((kbId: string) => {
    setDraftSettings((prev) => {
      const exists = prev.rag.knowledge_base_ids.includes(kbId);
      return {
        ...prev,
        rag: {
          ...prev.rag,
          knowledge_base_ids: exists
            ? prev.rag.knowledge_base_ids.filter((item) => item !== kbId)
            : [...prev.rag.knowledge_base_ids, kbId],
        },
      };
    });
    setKnowledgeBaseFeedback(null);
  }, []);

  const handleKnowledgeBaseModeChange = useCallback((mode: 'append' | 'override') => {
    setDraftSettings((prev) => ({
      ...prev,
      rag: {
        ...prev.rag,
        knowledge_base_mode: mode,
      },
    }));
    setKnowledgeBaseFeedback(null);
  }, []);

  const handleResetKnowledgeBases = useCallback(() => {
    setDraftSettings((prev) => ({
      ...prev,
      rag: currentSettings.rag,
    }));
    setKnowledgeBaseFeedback(null);
  }, [currentSettings.rag]);

  const handleSaveKnowledgeBases = useCallback(async () => {
    const nextSettings: ProjectSettings = {
      rag: {
        knowledge_base_mode: draftSettings.rag.knowledge_base_mode,
        knowledge_base_ids: normalizedSelection,
      },
      tools: {
        tool_enabled_map: { ...draftSettings.tools.tool_enabled_map },
      },
    };

    setSavingKnowledgeBases(true);
    setKnowledgeBaseFeedback(null);
    try {
      await persistProjectSettings(nextSettings);
      setKnowledgeBaseFeedback({
        type: 'success',
        message: t('workspace.settings.knowledgeBasesSaveSuccess'),
      });
    } catch (error) {
      console.error('Failed to save project knowledge base settings:', error);
      setKnowledgeBaseFeedback({
        type: 'error',
        message: t('workspace.settings.knowledgeBasesSaveFailed'),
      });
    } finally {
      setSavingKnowledgeBases(false);
    }
  }, [draftSettings.rag.knowledge_base_mode, draftSettings.tools.tool_enabled_map, normalizedSelection, persistProjectSettings, t]);

  const handleToolToggle = useCallback((toolKey: string) => {
    setDraftSettings((prev) => ({
      ...prev,
      tools: {
        tool_enabled_map: {
          ...prev.tools.tool_enabled_map,
          [toolKey]: !prev.tools.tool_enabled_map[toolKey],
        },
      },
    }));
    setToolFeedback(null);
  }, []);

  const handleResetTools = useCallback(() => {
    setDraftSettings((prev) => ({
      ...prev,
      tools: {
        tool_enabled_map: { ...currentSettings.tools.tool_enabled_map },
      },
    }));
    setToolFeedback(null);
  }, [currentSettings.tools.tool_enabled_map]);

  const handleSaveTools = useCallback(async () => {
    const nextSettings: ProjectSettings = {
      rag: {
        knowledge_base_mode: draftSettings.rag.knowledge_base_mode,
        knowledge_base_ids: normalizedSelection,
      },
      tools: {
        tool_enabled_map: { ...draftSettings.tools.tool_enabled_map },
      },
    };

    setSavingTools(true);
    setToolFeedback(null);
    try {
      await persistProjectSettings(nextSettings);
      setToolFeedback({
        type: 'success',
        message: t('workspace.settings.toolsSaveSuccess'),
      });
    } catch (error) {
      console.error('Failed to save project tool settings:', error);
      setToolFeedback({
        type: 'error',
        message: t('workspace.settings.toolsSaveFailed'),
      });
    } finally {
      setSavingTools(false);
    }
  }, [draftSettings.rag.knowledge_base_mode, draftSettings.tools.tool_enabled_map, normalizedSelection, persistProjectSettings, t]);

  return (
    <div
      data-name="project-settings-view"
      className="flex h-full min-h-0 w-full min-w-0 flex-1 flex-col overflow-hidden bg-gray-50 px-4 py-4 dark:bg-gray-950"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-gray-200 bg-white px-4 py-3 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="flex min-w-0 items-start gap-3">
          <div className="rounded-xl bg-gray-100 p-2 text-gray-700 dark:bg-gray-800 dark:text-gray-200">
            <Cog6ToothIcon className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{t('workspace.settings.title')}</h2>
            <p className="mt-0.5 text-sm text-gray-600 dark:text-gray-300">
              {t('workspace.settings.description', { projectName: currentProject?.name || projectId })}
            </p>
          </div>
        </div>
        {currentProject && (
          <div className="inline-flex items-center rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs font-medium text-gray-700 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200">
            {currentProject.name}
          </div>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="flex max-w-5xl flex-col gap-4">
          <section
            data-name="project-settings-knowledge-bases"
            className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900"
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-gray-100">
                  <BookOpenIcon className="h-4 w-4" />
                  {t('workspace.settings.knowledgeBasesTitle')}
                </div>
                <p className="mt-2 max-w-3xl text-sm text-gray-600 dark:text-gray-300">
                  {t('workspace.settings.knowledgeBasesDescription')}
                </p>
              </div>

              <button
                type="button"
                onClick={() => navigate('/settings/knowledge-bases')}
                className="inline-flex items-center gap-2 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-100 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
                data-name="project-settings-open-knowledge-bases"
              >
                {t('workspace.settings.openKnowledgeBases')}
              </button>
            </div>

            <div className="mt-5 grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
              <div className="rounded-2xl border border-gray-200 bg-gray-50/80 p-4 dark:border-gray-800 dark:bg-gray-950/40">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-gray-500 dark:text-gray-400">
                  {t('workspace.settings.knowledgeBaseModeLabel')}
                </div>
                <div className="mt-3 space-y-2">
                  {(['append', 'override'] as const).map((mode) => {
                    const active = draftSettings.rag.knowledge_base_mode === mode;
                    return (
                      <button
                        key={mode}
                        type="button"
                        onClick={() => handleKnowledgeBaseModeChange(mode)}
                        className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                          active
                            ? 'border-blue-300 bg-blue-50 text-blue-800 dark:border-blue-800 dark:bg-blue-900/20 dark:text-blue-200'
                            : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:bg-gray-800'
                        }`}
                        data-name={`project-settings-kb-mode-${mode}`}
                      >
                        <div className="text-sm font-semibold">{t(`workspace.settings.knowledgeBaseMode.${mode}.title`)}</div>
                        <div className="mt-1 text-xs text-current/80">
                          {t(`workspace.settings.knowledgeBaseMode.${mode}.description`)}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="rounded-2xl border border-gray-200 bg-gray-50/70 p-4 dark:border-gray-800 dark:bg-gray-950/30">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                    {t('workspace.settings.knowledgeBaseSelectionTitle')}
                  </div>
                  <button
                    type="button"
                    onClick={() => void loadKnowledgeBaseOptions()}
                    disabled={loadingKnowledgeBases || savingKnowledgeBases}
                    className="inline-flex items-center gap-2 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
                    data-name="project-settings-refresh-knowledge-bases"
                  >
                    <ArrowPathIcon className={`h-4 w-4 ${loadingKnowledgeBases ? 'animate-spin' : ''}`} />
                    {t('workspace.settings.refresh')}
                  </button>
                </div>

                <div className="mt-3 text-sm text-gray-600 dark:text-gray-300">
                  {loadingKnowledgeBases
                    ? t('chat.loading')
                    : knowledgeBaseLoadError || t('workspace.settings.knowledgeBaseSelectionCount', { count: normalizedSelection.length })}
                </div>

                <div className="mt-4 max-h-[320px] space-y-2 overflow-y-auto pr-1">
                  {!loadingKnowledgeBases && !knowledgeBaseLoadError && knowledgeBases.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-gray-300 px-4 py-5 text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
                      {t('workspace.settings.knowledgeBasesEmpty')}
                    </div>
                  ) : (
                    knowledgeBases.map((kb) => {
                      const selected = normalizedSelection.includes(kb.id);
                      return (
                        <button
                          key={kb.id}
                          type="button"
                          onClick={() => toggleKnowledgeBase(kb.id)}
                          className={`w-full rounded-xl border px-4 py-3 text-left transition ${
                            selected
                              ? 'border-blue-300 bg-blue-50 dark:border-blue-800 dark:bg-blue-900/20'
                              : 'border-gray-200 bg-white hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-900 dark:hover:bg-gray-800'
                          }`}
                          data-name="project-settings-kb-option"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0 flex-1">
                              <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">{kb.name}</div>
                              <div className="mt-1 break-words text-xs text-gray-500 dark:text-gray-400">{kb.id}</div>
                              {kb.description && (
                                <div className="mt-2 text-xs text-gray-600 dark:text-gray-300">{kb.description}</div>
                              )}
                            </div>
                            <div className={`rounded-full px-2 py-1 text-[11px] font-medium ${
                              selected
                                ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-200'
                                : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300'
                            }`}>
                              {selected ? t('workspace.settings.selected') : t('workspace.settings.notSelected')}
                            </div>
                          </div>
                        </button>
                      );
                    })
                  )}
                </div>

                <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-gray-200 pt-4 dark:border-gray-800">
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    {t('workspace.settings.knowledgeBaseScopeHint')}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={handleResetKnowledgeBases}
                      disabled={savingKnowledgeBases || !isKnowledgeBaseDirty}
                      className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
                      data-name="project-settings-reset-knowledge-bases"
                    >
                      {t('workspace.settings.reset')}
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleSaveKnowledgeBases()}
                      disabled={savingKnowledgeBases || loadingKnowledgeBases || Boolean(knowledgeBaseLoadError) || !isKnowledgeBaseDirty}
                      className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-400"
                      data-name="project-settings-save-knowledge-bases"
                    >
                      {savingKnowledgeBases ? t('workspace.settings.saving') : t('workspace.settings.save')}
                    </button>
                  </div>
                </div>

                {renderFeedback(knowledgeBaseFeedback, 'project-settings-kb-feedback')}
              </div>
            </div>
          </section>

          <section
            data-name="project-settings-tools"
            className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900"
          >
            <div className="flex items-start gap-3">
              <div className="rounded-xl bg-gray-100 p-2 text-gray-700 dark:bg-gray-800 dark:text-gray-200">
                <WrenchScrewdriverIcon className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">
                  {t('workspace.settings.toolsTitle')}
                </h3>
                <p className="mt-1 max-w-3xl text-sm text-gray-600 dark:text-gray-300">
                  {t('workspace.settings.toolsDescription')}
                </p>
                <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200">
                  {t('workspace.settings.toolsDefaultHint')}
                </div>
              </div>
            </div>

            <div className="mt-5 space-y-4">
              {loadingToolCatalog && (
                <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-600 dark:border-gray-800 dark:bg-gray-950/30 dark:text-gray-300">
                  {t('chat.loading')}
                </div>
              )}

              {toolCatalogLoadError && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-950/20 dark:text-red-300">
                  {toolCatalogLoadError}
                </div>
              )}

              {!loadingToolCatalog && !toolCatalogLoadError && groupedToolDefinitions.map(({
                group,
                title_i18n_key,
                description_i18n_key,
                tools: items,
              }) => (
                <section
                  key={group}
                  className="rounded-2xl border border-gray-200 bg-gray-50/70 p-4 dark:border-gray-800 dark:bg-gray-950/30"
                  data-name={`project-settings-tool-group-${group}`}
                >
                  <div className="mb-3">
                    <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                      {t(title_i18n_key)}
                    </div>
                    <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      {t(description_i18n_key)}
                    </div>
                  </div>

                  <div className="space-y-2">
                    {items.map((tool) => {
                      const enabled = Boolean(draftSettings.tools.tool_enabled_map[tool.name]);
                      const disabledByContext = Boolean(tool.requires_project_knowledge && knowledgeToolsDefinitelyUnavailable);
                      const reason = disabledByContext ? t('workspace.settings.toolUnavailableKnowledge') : null;
                      return (
                        <div
                          key={tool.name}
                          className={`rounded-xl border px-4 py-3 ${
                            disabledByContext
                              ? 'border-gray-200 bg-gray-100/80 opacity-70 dark:border-gray-800 dark:bg-gray-900/60'
                              : enabled
                                ? 'border-blue-200 bg-blue-50/80 dark:border-blue-900/50 dark:bg-blue-950/20'
                                : 'border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900'
                          }`}
                          data-name="project-settings-tool-item"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0 flex-1">
                              <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                                {t(tool.title_i18n_key)}
                              </div>
                              <div className="mt-1 text-xs text-gray-600 dark:text-gray-300">
                                {t(tool.description_i18n_key)}
                              </div>
                              {reason && (
                                <div className="mt-2 text-xs text-amber-700 dark:text-amber-300">{reason}</div>
                              )}
                            </div>
                            <button
                              type="button"
                              onClick={() => handleToolToggle(tool.name)}
                              disabled={disabledByContext || savingTools}
                              className={`inline-flex min-w-[88px] items-center justify-center rounded-lg px-3 py-2 text-sm font-medium transition ${
                                enabled
                                  ? 'bg-blue-600 text-white hover:bg-blue-700 disabled:bg-blue-400'
                                  : 'border border-gray-300 bg-white text-gray-700 hover:bg-gray-100 disabled:border-gray-200 disabled:text-gray-400 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:bg-gray-800'
                              } disabled:cursor-not-allowed disabled:opacity-70`}
                              data-name={`project-settings-toggle-tool-${tool.name}`}
                            >
                              {enabled ? t('workspace.settings.enabled') : t('workspace.settings.disabled')}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </section>
              ))}
            </div>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-gray-200 pt-4 dark:border-gray-800">
              <div className="text-xs text-gray-500 dark:text-gray-400">
                {t('workspace.settings.toolsScopeHint')}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={handleResetTools}
                  disabled={loadingToolCatalog || savingTools || !isToolDirty}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
                  data-name="project-settings-reset-tools"
                >
                  {t('workspace.settings.reset')}
                </button>
                <button
                  type="button"
                  onClick={() => void handleSaveTools()}
                  disabled={loadingToolCatalog || savingTools || !isToolDirty}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-blue-400"
                  data-name="project-settings-save-tools"
                >
                  {savingTools ? t('workspace.settings.saving') : t('workspace.settings.save')}
                </button>
              </div>
            </div>

            {renderFeedback(toolFeedback, 'project-settings-tool-feedback')}
          </section>

          <section
            data-name="project-settings-chat-history"
            className="rounded-2xl border border-red-200 bg-white p-5 shadow-sm dark:border-red-900/50 dark:bg-gray-900"
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-sm font-semibold text-red-700 dark:text-red-300">
                  <ChatBubbleLeftRightIcon className="h-4 w-4" />
                  {t('workspace.settings.chatHistoryTitle')}
                </div>
                <p className="mt-2 max-w-2xl text-sm text-gray-600 dark:text-gray-300">
                  {t('workspace.settings.chatHistoryDescription')}
                </p>
              </div>

              <button
                type="button"
                onClick={() => void loadSessionCount()}
                disabled={loadingCount || deleting}
                className="inline-flex items-center gap-2 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
                data-name="project-settings-refresh-count"
              >
                <ArrowPathIcon className={`h-4 w-4 ${loadingCount ? 'animate-spin' : ''}`} />
                {t('workspace.settings.refresh')}
              </button>
            </div>

            <div className="mt-5 rounded-2xl border border-red-100 bg-red-50/70 p-4 dark:border-red-900/40 dark:bg-red-950/20">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-red-700 dark:text-red-300">
                    {t('workspace.settings.dangerZone')}
                  </div>
                  <div className="mt-2 text-sm text-gray-700 dark:text-gray-200">
                    {loadingCount
                      ? t('chat.loading')
                      : loadError || t('workspace.settings.chatHistoryCount', { count: sessionCount })}
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => void handleDeleteAllConversations()}
                  disabled={deleting || loadingCount || sessionCount === 0}
                  className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-red-400 disabled:text-red-100 dark:disabled:bg-red-900/50"
                  data-name="project-settings-delete-all-conversations"
                >
                  <TrashIcon className="h-4 w-4" />
                  {deleting
                    ? t('workspace.settings.deleteAllConversationsRunning')
                    : t('workspace.settings.deleteAllConversations')}
                </button>
              </div>

              {renderFeedback(feedback, 'project-settings-feedback')}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};
